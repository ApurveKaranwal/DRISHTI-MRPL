"""
Local synthetic refinery telemetry simulator.

The simulator is intentionally independent from the frontend.

Flow:

    ScenarioEngine
          ↓
    Sensor generator
          ↓
    Risk engine
          ↓
    RuntimeStore
          ↓
    FastAPI runtime endpoints
          ↓
    Dashboard

Nothing in this module makes network requests.
"""

from __future__ import annotations

import argparse
import random
from collections import deque
import threading
import time
from typing import Optional

from .config import RUNTIME_SITES, SIMULATOR_CONFIG
from .risk_engine import RiskEngine
from .scenarios import Scenario, ScenarioEngine
from .sensors import (
    SensorReading,
    create_reading,
    is_valid_reading,
    utc_now_iso,
)
from .store import RuntimeStore


class RuntimeSimulator:

    def __init__(
        self,
        *,
        store: RuntimeStore | None = None,
        scenario_engine: ScenarioEngine | None = None,
        risk_engine: RiskEngine | None = None,

        interval_seconds: float | None = None,

        site_id: str | None = None,

        plant: str | None = None,

        unit: str | None = None,

        source: str | None = None,

        seed: int | None = None,
    ) -> None:

        self.interval_seconds = (
            float(interval_seconds)
            if interval_seconds is not None
            else float(
                SIMULATOR_CONFIG[
                    "interval_seconds"
                ]
            )
        )

        if self.interval_seconds < 0.25:

            raise ValueError(
                "interval_seconds must be >= 0.25"
            )

        self.site_id = (
            site_id
            or SIMULATOR_CONFIG.get(
                "site_id",
                "MRPL_MANGALORE_DEMO",
            )
        )
        self.site = RUNTIME_SITES.get(self.site_id)
        if self.site is None:
            raise ValueError(
                f"Unknown runtime site: {self.site_id}"
            )

        self.site_name = self.site["name"]
        self.site_location = self.site.get("location", "")

        self.plant = (
            plant
            or self.site.get("plant", SIMULATOR_CONFIG["plant"])
        )

        self.unit = (
            unit
            or self.site.get("default_unit", SIMULATOR_CONFIG["unit"])
        )

        self.source = (
            source
            or SIMULATOR_CONFIG[
                "source"
            ]
        )

        self.assets = list(
            self.site.get(
                "assets",
                SIMULATOR_CONFIG["assets"],
            )
        )
        self.store = (
            store
            or RuntimeStore(
                 max_records_per_asset=300,
                retention_minutes=60,
                storage_path=(
                    SIMULATOR_CONFIG[
                        "history_file"
                    ]
                ),
                persist=True,
                load_existing=False,
            )
        )

        



        """self.store = (
            store
            or RuntimeStore(
                max_records=int(
                    SIMULATOR_CONFIG[
                        "memory_records"
                    ]
                ),
                storage_path=(
                    SIMULATOR_CONFIG[
                        "history_file"
                    ]
                ),
                persist=True,
                load_existing=False,
            )
        )""" 

        self.scenario_engine = (
            scenario_engine
            or ScenarioEngine()
        )

        self.risk_engine = (
            risk_engine
            or RiskEngine()
        )

        self._rng = random.Random(
            seed
        )

        self._stop_event = (
            threading.Event()
        )

        self._thread: Optional[
            threading.Thread
        ] = None

        self._lock = (
            threading.RLock()
        )

        self._sequence = (
            self.store.last_sequence()
            or 0
        )

        self._asset_states: dict[
            str,
            dict[str, float]
        ] = {}

        self._last_readings: dict[
            str,
            SensorReading
        ] = {}

        self._last_error: str | None = (
            None
        )

        self._started_monotonic: (
            float | None
        ) = None

        # Runtime observability state. These are intentionally bounded
        # so the demo cannot grow memory forever.
        self._last_asset_risks: dict[str, dict] = {}
        self._active_alert_keys: set[tuple[str, str]] = set()
        self._events = deque(maxlen=200)

    # ========================================================
    # LIFECYCLE
    # ========================================================

    @property
    def running(self) -> bool:

        return bool(
            self._thread
            and self._thread.is_alive()
        )

    def start(self) -> None:

        with self._lock:

            if self.running:
                return

            self._stop_event.clear()

            self._started_monotonic = (
                time.monotonic()
            )

            self._thread = threading.Thread(
                target=self._run,
                name=(
                    "drishti-runtime-"
                    "simulator"
                ),
                daemon=True,
            )

            self._thread.start()

    def stop(
        self,
        timeout: float = 3.0,
    ) -> None:

        self._stop_event.set()

        thread = self._thread

        if thread:

            thread.join(
                timeout=timeout
            )

        with self._lock:

            self._thread = None

    # ========================================================
    # SCENARIOS
    # ========================================================

    def set_scenario(
        self,
        scenario: Scenario | str,
    ) -> dict:

        metadata = self.scenario_engine.set(scenario)
        self._push_event(
            "SCENARIO",
            f"Scenario applied: {metadata['name'].replace('_', ' ')}",
            severity="INFO",
        )
        return metadata

    def _push_event(
        self,
        event_type: str,
        message: str,
        *,
        asset_id: str | None = None,
        severity: str = "INFO",
    ) -> None:
        self._events.append({
            "timestamp": utc_now_iso(),
            "type": event_type,
            "asset_id": asset_id,
            "severity": severity,
            "message": message,
        })

    @staticmethod
    def _alert_severity(risk: dict, message: str) -> str:
        upper = str(message).upper()
        if risk.get("emergency") or float(risk.get("score", 0)) >= 80 or upper.startswith("CRITICAL"):
            return "CRITICAL"
        if "HIGH-RISK" in upper or str(risk.get("status", "")).upper() == "WARNING" or float(risk.get("score", 0)) >= 60:
            return "WARNING"
        return "WATCH"

    @staticmethod
    def _is_alert_active(risk: dict, message: str) -> bool:
        score = float(risk.get("score", 0) or 0)
        upper = str(message).upper()
        return bool(
            risk.get("emergency")
            or score >= 30
            or "CRITICAL" in upper
            or "HIGH-RISK" in upper
        )

    # ========================================================
    # GENERATION
    # ========================================================

    def generate_tick(
        self,
    ) -> list[dict]:

        '''offsets = (
            self.scenario_engine.offsets()
        )'''

        records = []
        tick_alert_keys: set[tuple[str, str]] = set()

        # One complete telemetry stream tick.
        # Every asset gets a timestamped sample.

        for asset in self.assets:
            
            

            self._sequence += 1

            asset_id = asset[
                "asset_id"
            ]
            asset_offsets = (
                self.scenario_engine
                .offsets_for_asset(
                    asset_id=asset["asset_id"]
                )
            )



            previous_state = (
                self._asset_states.get(
                    asset_id
                )
            )

            reading = create_reading(

                rng=self._rng,

                sequence=self._sequence,

                plant=self.plant,

                unit=(
                    asset_id
                    if asset[
                        "asset_type"
                    ]
                    == "PROCESS_UNIT"
                    else self.unit
                ),

                asset_id=asset_id,

                asset_type=asset[
                    "asset_type"
                ],

                equipment=asset[
                    "equipment"
                ],

                source=self.source,

                scenario_offsets=asset_offsets,

                state_memory=previous_state,
            )

            if not is_valid_reading(
                reading
            ):

                raise ValueError(
                    "Generated invalid "
                    "telemetry record."
                )

            # Store current numeric state so next
            # tick has temporal continuity.

            self._asset_states[
                asset_id
            ] = {

                key: float(value)

                for key, value
                in reading.to_dict().items()

                if key
                in {
                    "reactor_temperature_c",
                    "reactor_pressure_bar",
                    "flow_rate_m3_h",
                    "feed_rate_t_h",
                    "pump_vibration_mm_s",
                    "bearing_temperature_c",
                    "pump_rpm",
                    "energy_consumption_mw",
                    "valve_position_pct",
                    "level_pct",
                    "h2s_ppm",
                    "so2_ppm",
                    "nox_ppm",
                }
            }


            history = (
                self.store.readings(
                    limit=20,
                    asset_id=asset_id,
                )
            )

            """history = (
                self.store.readings(
                    limit=20
                )
            )"""

            risk = (
                self.risk_engine.assess(
                    reading,
                    history + [reading],
                )
            )

            record = self.store.append(
                reading,
                risk,
            )

            self._last_readings[
                asset_id
            ] = reading

            current_risk = dict(record.get("risk", {}))
            previous_risk = self._last_asset_risks.get(asset_id)
            current_status = current_risk.get("status", "NORMAL")

            if previous_risk is not None:
                previous_status = previous_risk.get("status", "NORMAL")
                if previous_status != current_status:
                    self._push_event(
                        "RISK_CHANGE",
                        f"{asset_id} risk changed {previous_status} → {current_status} ({current_risk.get('score', 0):.0f}/100)",
                        asset_id=asset_id,
                        severity=current_status,
                    )

            for alert_message in current_risk.get("alerts", []):
                alert_message = str(alert_message)
                if self._is_alert_active(current_risk, alert_message):
                    tick_alert_keys.add((asset_id, alert_message))

            self._last_asset_risks[asset_id] = current_risk

            records.append(
                record
            )

        # Alert lifecycle events are calculated after the complete tick,
        # so one asset cannot temporarily make another asset look resolved.
        new_alerts = tick_alert_keys - self._active_alert_keys
        resolved_alerts = self._active_alert_keys - tick_alert_keys

        for asset_id, message in sorted(new_alerts):
            risk = self._last_asset_risks.get(asset_id, {})
            self._push_event(
                "ALERT_RAISED",
                message,
                asset_id=asset_id,
                severity=self._alert_severity(risk, message),
            )

        for asset_id, message in sorted(resolved_alerts):
            self._push_event(
                "ALERT_RESOLVED",
                message,
                asset_id=asset_id,
                severity="RESOLVED",
            )

        self._active_alert_keys = tick_alert_keys
        self._last_error = None

        return records

    # ========================================================
    # BACKGROUND LOOP
    # ========================================================

    def _run(self) -> None:

        while not self._stop_event.is_set():

            started = time.monotonic()

            try:

                self.generate_tick()

            except Exception as exc:

                with self._lock:

                    self._last_error = (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

            elapsed = (
                time.monotonic()
                - started
            )

            wait_time = max(
                0.05,
                self.interval_seconds
                - elapsed,
            )

            self._stop_event.wait(
                wait_time
            )

    # ========================================================
    # STATUS
    # ========================================================

    def latest(
        self,
        asset_id: str | None = None,
    ) -> dict | None:

        return self.store.latest(asset_id=asset_id)

    def _latest_asset_records(self) -> list[dict]:
        result = []
        for asset in self.assets:
            record = self.store.latest(asset_id=asset["asset_id"])
            if record is not None:
                result.append(record)
        return result

    def _active_alerts(self, asset_records: list[dict]) -> list[dict]:
        alerts = []
        seen = set()
        for record in asset_records:
            reading = record.get("reading", {})
            risk = record.get("risk", {})
            asset_id = reading.get("asset_id", "UNKNOWN")
            for message in risk.get("alerts", []):
                message = str(message)
                if not self._is_alert_active(risk, message):
                    continue
                key = (asset_id, message)
                if key in seen:
                    continue
                seen.add(key)
                alerts.append({
                    "asset_id": asset_id,
                    "severity": self._alert_severity(risk, str(message)),
                    "message": str(message),
                    "timestamp": reading.get("timestamp"),
                    "sequence": reading.get("sequence"),
                    "status": "ACTIVE",
                    "risk_score": risk.get("score", 0),
                })
        order = {"CRITICAL": 0, "WARNING": 1, "WATCH": 2}
        alerts.sort(key=lambda a: (order.get(a["severity"], 9), -(int(a.get("sequence") or 0))))
        return alerts

    def live_state(self, focus_asset_id: str | None = None) -> dict:
        asset_records = self._latest_asset_records()

        if asset_records:
            highest = max(
                asset_records,
                key=lambda r: float(r.get("risk", {}).get("score", 0)),
            )
            plant_risk = dict(highest.get("risk", {}))
            plant_risk["asset_id"] = highest.get("reading", {}).get("asset_id")
        else:
            highest = None
            plant_risk = {
                "score": 0.0,
                "status": "NORMAL",
                "primary_risk": "Waiting for telemetry",
                "recommendation": "Start the local simulator to collect telemetry.",
                "alerts": [],
                "contributors": [],
                "emergency": False,
                "band_states": {},
                "asset_id": None,
            }

        requested = focus_asset_id if focus_asset_id in {r.get("reading", {}).get("asset_id") for r in asset_records} else None
        focus_record = next((r for r in asset_records if r.get("reading", {}).get("asset_id") == requested), None) if requested else highest

        assets_payload = []
        for asset in self.assets:
            asset_id = asset["asset_id"]
            record = next((r for r in asset_records if r.get("reading", {}).get("asset_id") == asset_id), None)
            assets_payload.append({
                "asset_id": asset_id,
                "asset_type": asset.get("asset_type"),
                "equipment": asset.get("equipment"),
                "reading": record.get("reading") if record else None,
                "risk": record.get("risk") if record else {"score": 0, "status": "WAITING", "alerts": [], "contributors": []},
            })

        focus_asset = None
        history = []
        if focus_record:
            focus_asset_id = focus_record["reading"]["asset_id"]
            focus_asset = {
                "asset_id": focus_asset_id,
                "asset_type": focus_record["reading"].get("asset_type"),
                "equipment": focus_record["reading"].get("equipment"),
                "reading": focus_record["reading"],
                "risk": focus_record["risk"],
            }
            history = self.store.history(
                limit=min(60, int(SIMULATOR_CONFIG["api_history_limit"])),
                asset_id=focus_asset_id,
            )

        latest_global = self.store.latest()

        return {
            "timestamp": (
                latest_global.get("reading", {}).get("timestamp")
                if latest_global else None
            ),
            "site": {
                "id": self.site_id,
                "name": self.site_name,
                "location": self.site_location,
                "data_mode": "LIVE_SCADA_TELEMETRY",
            },
            "unit": {
                "id": self.unit,
                "name": self.site.get("unit_name", self.unit),
            },
            "source": {
                "type": "mrpl_scada_gateway",
                "label": "MRPL Real-Time SCADA Gateway",
                "external_network_required": False,
            },
            "simulator": self.status(),
            "scenario": self.scenario_engine.metadata(),
            "plant_risk": plant_risk,
            "assets": assets_payload,
            "focus_asset_id": focus_asset.get("asset_id") if focus_asset else None,
            "focus_asset": focus_asset,
            "history": history,
            "alerts": self._active_alerts(asset_records),
            "events": list(reversed(self._events))[:40],
            "latest": latest_global,
        }

    def status(self) -> dict:
        latest = self.store.latest()
        scenario = self.scenario_engine.metadata()

        return {
            "running": self.running,
            "site_id": self.site_id,
            "site_name": self.site_name,
            "site_location": self.site_location,
            "plant": self.plant,
            "unit": self.unit,
            "source": self.source,
            "interval_seconds": self.interval_seconds,
            "scenario": scenario,
            "records_available": self.store.count(),
            "latest_timestamp": latest["reading"]["timestamp"] if latest else None,
            "latest_sequence": latest["reading"]["sequence"] if latest else None,
            "asset_count": len(self.assets),
            "assets": [asset["asset_id"] for asset in self.assets],
            "last_error": self._last_error,
            "source_type": "mrpl_scada_gateway",
            "external_network_required": False,
        }

    def dashboard_state(self) -> dict:
        state = self.live_state()
        return {
            **state,
            "risk": state["plant_risk"],
        }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "DRISHTI-MRPL synthetic runtime "
            "refinery telemetry simulator"
        )
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=None,
    )

    parser.add_argument(
        "--scenario",
        default="NORMAL",
    )

    parser.add_argument(
        "--seconds",
        type=float,
        default=0.0,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
    )

    args = parser.parse_args()

    simulator = RuntimeSimulator(
        interval_seconds=args.interval,
        seed=args.seed,
    )

    simulator.set_scenario(
        args.scenario
    )

    simulator.start()

    print(
        "\nDRISHTI-MRPL "
        "Runtime Telemetry Simulator"
    )

    print(
        "MRPL On-Premises Telemetry."
    )

    print(
        "No external network connection is "
        "required by the simulator."
    )

    print(
        f"Scenario: {args.scenario}"
    )

    print(
        f"Interval: "
        f"{simulator.interval_seconds:.1f}s"
    )

    print(
        "Press Ctrl+C to stop.\n"
    )

    try:

        if args.seconds > 0:

            time.sleep(
                args.seconds
            )

        else:

            while True:

                time.sleep(
                    1
                )

    except KeyboardInterrupt:

        print(
            "\nStopping..."
        )

    finally:

        simulator.stop()


if __name__ == "__main__":
    main()