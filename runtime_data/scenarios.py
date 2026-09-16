"""
Controlled refinery operating scenarios for simulation.

Operational refinery failure modes and transient upset dynamics calibrated against API and OISD engineering thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
import time
from typing import Dict


class Scenario(str, Enum):
    NORMAL = "NORMAL"
    PUMP_DEGRADATION = "PUMP_DEGRADATION"
    HIGH_TEMPERATURE = "HIGH_TEMPERATURE"
    PRESSURE_SURGE = "PRESSURE_SURGE"
    GAS_LEAK = "GAS_LEAK"
    COOLING_FAILURE = "COOLING_FAILURE"
    LOAD_INCREASE = "LOAD_INCREASE"


@dataclass(frozen=True)
class ScenarioConfig:
    name: Scenario
    description: str

    # Sensor changes caused by this scenario.
    offsets: Dict[str, float]

    # Assets affected by the scenario.
    affected_assets: tuple[str, ...]

    # Time required for the scenario to reach full intensity.
    ramp_seconds: float


SCENARIO_CONFIGS: Dict[Scenario, ScenarioConfig] = {

    # ---------------------------------------------------------
    # NORMAL
    # ---------------------------------------------------------

    Scenario.NORMAL: ScenarioConfig(
        name=Scenario.NORMAL,
        description=(
            "Stable synthetic plant operation "
            "with natural sensor variation."
        ),
        offsets={},
        affected_assets=(),
        ramp_seconds=1.0,
    ),

    # ---------------------------------------------------------
    # PUMP DEGRADATION
    # ---------------------------------------------------------

    Scenario.PUMP_DEGRADATION: ScenarioConfig(
        name=Scenario.PUMP_DEGRADATION,
        description=(
            "Progressive degradation of pump P-101. "
            "Vibration and bearing temperature rise "
            "while effective flow decreases."
        ),
        offsets={
            "pump_vibration_mm_s": 5.4,
            "bearing_temperature_c": 24.0,
            "flow_rate_m3_h": -65.0,
            "pump_rpm": -45.0,
            "energy_consumption_mw": 0.65,
        },

        # IMPORTANT:
        # Only P-101 is degraded.
        affected_assets=("P-101",),

        ramp_seconds=45.0,
    ),

    # ---------------------------------------------------------
    # HIGH TEMPERATURE
    # ---------------------------------------------------------

    Scenario.HIGH_TEMPERATURE: ScenarioConfig(
        name=Scenario.HIGH_TEMPERATURE,
        description=(
            "Progressive process-temperature increase "
            "with secondary process stress."
        ),
        offsets={
            "reactor_temperature_c": 28.0,
            "reactor_pressure_bar": 2.5,
            "energy_consumption_mw": 0.55,
            "bearing_temperature_c": 5.5,
        },

        # Process unit is the primary affected asset.
        affected_assets=("CDU-01",),

        ramp_seconds=35.0,
    ),

    # ---------------------------------------------------------
    # PRESSURE SURGE
    # ---------------------------------------------------------

    Scenario.PRESSURE_SURGE: ScenarioConfig(
        name=Scenario.PRESSURE_SURGE,
        description=(
            "Progressive pressure increase "
            "with corresponding process stress."
        ),
        offsets={
            "reactor_pressure_bar": 0.38,
            "reactor_temperature_c": 6.0,
            "valve_position_pct": 8.0,
            "energy_consumption_mw": 0.35,
        },

        affected_assets=("CDU-01",),

        ramp_seconds=22.0,
    ),

    # ---------------------------------------------------------
    # GAS LEAK
    # ---------------------------------------------------------

    Scenario.GAS_LEAK: ScenarioConfig(
        name=Scenario.GAS_LEAK,
        description=(
            "Progressive synthetic H2S concentration rise."
        ),
        offsets={
            "h2s_ppm": 16.0,
            "flow_rate_m3_h": -15.0,
        },

        affected_assets=("CDU-01",),

        ramp_seconds=30.0,
    ),

    # ---------------------------------------------------------
    # COOLING FAILURE
    # ---------------------------------------------------------

    Scenario.COOLING_FAILURE: ScenarioConfig(
        name=Scenario.COOLING_FAILURE,
        description=(
            "Cooling performance deterioration "
            "causes temperature and pressure to rise."
        ),
        offsets={
            "reactor_temperature_c": 24.0,
            "reactor_pressure_bar": 4.0,
            "bearing_temperature_c": 9.0,
            "energy_consumption_mw": 0.45,
        },

        affected_assets=("CDU-01", "HE-201"),

        ramp_seconds=35.0,
    ),

    # ---------------------------------------------------------
    # LOAD INCREASE
    # ---------------------------------------------------------

    Scenario.LOAD_INCREASE: ScenarioConfig(
        name=Scenario.LOAD_INCREASE,
        description=(
            "Synthetic production-load increase "
            "raising feed, flow, temperature, and energy use."
        ),
        offsets={
            "feed_rate_t_h": 12.0,
            "flow_rate_m3_h": 14.0,
            "reactor_temperature_c": 7.0,
            "reactor_pressure_bar": 1.5,
            "energy_consumption_mw": 0.75,
        },

        # Load increase affects the process unit.
        affected_assets=("CDU-01",),

        ramp_seconds=30.0,
    ),
}


class ScenarioEngine:

    def __init__(
        self,
        initial: Scenario | str = Scenario.NORMAL,
    ) -> None:

        self._lock = threading.RLock()

        self._scenario = self._coerce(initial)

        self._started = time.monotonic()

    @staticmethod
    def _coerce(
        scenario: Scenario | str,
    ) -> Scenario:

        if isinstance(scenario, Scenario):
            return scenario

        try:
            val = str(scenario).strip().upper()
            if val == "NOMINAL":
                val = "NORMAL"
            return Scenario(val)

        except ValueError as exc:

            valid = ", ".join(
                scenario.value
                for scenario in Scenario
            )

            raise ValueError(
                f"Unknown scenario {scenario!r}. "
                f"Valid scenarios: {valid}"
            ) from exc

    def set(
        self,
        scenario: Scenario | str,
    ) -> dict:

        with self._lock:

            self._scenario = self._coerce(
                scenario
            )

            self._started = time.monotonic()

            return self.metadata()

    def get(self) -> Scenario:

        with self._lock:
            return self._scenario

    def elapsed(self) -> float:

        with self._lock:

            return max(
                0.0,
                time.monotonic()
                - self._started,
            )

    def progress(self) -> float:

        config = SCENARIO_CONFIGS[
            self.get()
        ]

        return min(
            1.0,
            self.elapsed()
            / max(
                1.0,
                config.ramp_seconds,
            ),
        )

    def offsets(self) -> Dict[str, float]:
        """
        Return scenario offsets for the currently
        active scenario.

        NOTE:
        This method is kept for compatibility.
        For asset-specific simulation use
        offsets_for_asset().
        """

        config = SCENARIO_CONFIGS[
            self.get()
        ]

        progress = self.progress()

        # Smooth ramp.
        smooth = (
            progress
            * progress
            * (3.0 - 2.0 * progress)
        )

        return {
            key: value * smooth
            for key, value in config.offsets.items()
        }

    def offsets_for_asset(
        self,
        asset_id: str,
    ) -> Dict[str, float]:
        """
        Return scenario offsets ONLY if this asset
        is affected by the active scenario.

        This prevents a pump failure scenario
        from accidentally affecting every asset.
        """

        config = SCENARIO_CONFIGS[
            self.get()
        ]

        if asset_id not in config.affected_assets:
            return {}

        progress = self.progress()

        # Smooth 0 -> 1 transition.
        smooth = (
            progress
            * progress
            * (3.0 - 2.0 * progress)
        )

        return {
            key: value * smooth
            for key, value in config.offsets.items()
        }

    def metadata(self) -> dict:

        config = SCENARIO_CONFIGS[
            self.get()
        ]

        progress = self.progress()

        return {
            "name": config.name.value,

            "description": config.description,

            "progress_pct": round(
                progress * 100.0,
                1,
            ),

            "ramp_seconds": (
                config.ramp_seconds
            ),

            "elapsed_seconds": round(
                self.elapsed(),
                1,
            ),

            "affected_assets": list(
                config.affected_assets
            ),
        }

    @staticmethod
    def available() -> list[dict]:

        return [
            {
                "name": config.name.value,

                "description": config.description,

                "ramp_seconds": (
                    config.ramp_seconds
                ),

                "affected_assets": list(
                    config.affected_assets
                ),
            }

            for config in SCENARIO_CONFIGS.values()
        ]