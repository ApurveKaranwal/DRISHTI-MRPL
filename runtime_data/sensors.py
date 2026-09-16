"""
Runtime telemetry schemas and sensor generation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
import random
from typing import Any, Mapping

from .config import BASELINE, HARD_BOUNDS, NOISE_STD


@dataclass(frozen=True)
class SensorReading:
    """One complete synthetic industrial telemetry sample."""

    timestamp: str
    sequence: int

    plant: str
    unit: str
    asset_id: str
    asset_type: str
    equipment: str
    source: str

    # Process
    reactor_temperature_c: float
    reactor_pressure_bar: float
    flow_rate_m3_h: float
    feed_rate_t_h: float

    # Rotating equipment
    pump_vibration_mm_s: float
    bearing_temperature_c: float
    pump_rpm: float

    # Utilities/control
    energy_consumption_mw: float
    valve_position_pct: float
    level_pct: float

    # Environment/safety
    h2s_ppm: float
    so2_ppm: float
    nox_ppm: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlantSnapshot:
    """
    Current runtime state for API/UI consumption.
    """

    timestamp: str
    scenario: str
    source_status: str

    reading: SensorReading | None

    records_available: int
    simulator_running: bool

    risk: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "scenario": self.scenario,
            "source_status": self.source_status,
            "reading": (
                self.reading.to_dict()
                if self.reading
                else None
            ),
            "records_available": self.records_available,
            "simulator_running": self.simulator_running,
            "risk": self.risk,
        }


def utc_now_iso() -> str:
    """Return a UTC ISO-8601 timestamp."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def clamp_sensor(
    name: str,
    value: float,
) -> float:
    """Keep a generated value inside hard simulation bounds."""

    low, high = HARD_BOUNDS[name]

    return max(
        low,
        min(high, value),
    )


def safe_number(value: float) -> float:
    """Prevent NaN/Inf values from entering telemetry."""

    if not math.isfinite(value):
        return 0.0

    return value


def generate_sensor_values(
    *,
    rng: random.Random,
    scenario_offsets: Mapping[str, float],
    state_memory: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """
    Generate a physically-inspired synthetic plant state.

    The generator combines:

    baseline
    + scenario effect
    + small natural noise
    + cross-variable relationships

    It does NOT use completely independent random values.
    """

    state_memory = state_memory or {}

    values: dict[str, float] = {}

    # ---------------------------------------------------------
    # Baseline + scenario offset + noise
    # ---------------------------------------------------------

    for name, baseline in BASELINE.items():

        previous = float(
            state_memory.get(
                name,
                baseline,
            )
        )

        target = (
            baseline
            + float(
                scenario_offsets.get(
                    name,
                    0.0,
                )
            )
        )

        # Move gradually toward target instead of teleporting.
        inertia = 0.25

        value = (
            previous
            + (target - previous) * inertia
            + rng.gauss(
                0.0,
                NOISE_STD[name],
            )
        )

        values[name] = clamp_sensor(
            name,
            safe_number(value),
        )

    # ---------------------------------------------------------
    # Cross-variable relationships
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # Cross-variable relationships
    # ---------------------------------------------------------

    # The relationships below are target-based rather than
    # cumulative. This prevents values from "running away"
    # toward the hard bounds over time.

    feed_delta = (
     values["feed_rate_t_h"]
        - BASELINE["feed_rate_t_h"]
    )

# ---------------------------------------------------------
# Feed rate -> flow
# ---------------------------------------------------------

    flow_target = (
        BASELINE["flow_rate_m3_h"]
        + feed_delta * 0.55
        + scenario_offsets.get(
            "flow_rate_m3_h",
            0.0,
        )
    )


    values["flow_rate_m3_h"] = clamp_sensor(
        "flow_rate_m3_h",
        (
            values["flow_rate_m3_h"] * 0.70
            + flow_target * 0.30
        ),
    )


# ---------------------------------------------------------
# Feed / process load -> energy
# ---------------------------------------------------------

    energy_target = (
        BASELINE["energy_consumption_mw"]
        + max(
            -1.0,
            min(
                1.0,
                feed_delta * 0.018,
            ),
        )
    
    + scenario_offsets.get(
            "energy_consumption_mw",
            0.0,
        )
    )


    values["energy_consumption_mw"] = clamp_sensor(
        "energy_consumption_mw",
        (
            values["energy_consumption_mw"] * 0.75
            + energy_target * 0.25
        ),
    )

# ---------------------------------------------------------
# Flow -> reactor temperature
# ---------------------------------------------------------

    flow_delta = (
        values["flow_rate_m3_h"]
        - BASELINE["flow_rate_m3_h"]
    )

    temperature_target = (
        BASELINE["reactor_temperature_c"]
        + flow_delta * 0.035
        + scenario_offsets.get(
            "reactor_temperature_c",
            0.0,
        )
    )


    values["reactor_temperature_c"] = clamp_sensor(
        "reactor_temperature_c",
        (
            values["reactor_temperature_c"] * 0.75
            + temperature_target * 0.25
        ),
    )

# ---------------------------------------------------------
# Pump vibration -> bearing temperature
# ---------------------------------------------------------

    vibration_delta = max(
        0.0,
        values["pump_vibration_mm_s"]
        - BASELINE["pump_vibration_mm_s"],
    )

    bearing_target = (
        BASELINE["bearing_temperature_c"]
        + scenario_offsets.get(
            "bearing_temperature_c",
            0.0,
        )
    
        + vibration_delta * 2.0
    )

    values["bearing_temperature_c"] = clamp_sensor(
        "bearing_temperature_c",
        (
            values["bearing_temperature_c"] * 0.80
            + bearing_target * 0.20
        ),
    )

# ---------------------------------------------------------
# Pump degradation -> effective flow
# ---------------------------------------------------------

    if vibration_delta > 0.5:

        degradation_factor = min(
            8.0,
            vibration_delta * 1.5,
        )
    

        flow_after_degradation = (
            values["flow_rate_m3_h"]
            - degradation_factor
        )

        values["flow_rate_m3_h"] = clamp_sensor(
            "flow_rate_m3_h",
            flow_after_degradation,
        )


    ''' 
    feed_delta = (
        values["feed_rate_t_h"]
        - BASELINE["feed_rate_t_h"]
    )

    # Higher feed tends to increase flow.
    values["flow_rate_m3_h"] = clamp_sensor(
        "flow_rate_m3_h",
        values["flow_rate_m3_h"]
        + feed_delta * 0.55,
    )

    # Higher feed increases energy load modestly.
    values["energy_consumption_mw"] = clamp_sensor(
        "energy_consumption_mw",
        values["energy_consumption_mw"]
        + max(
            -1.0,
            min(
                1.0,
                feed_delta * 0.018,
            ),
        ),
    )

    # Higher flow tends to produce slightly higher process temperature.
    flow_delta = (
        values["flow_rate_m3_h"]
        - BASELINE["flow_rate_m3_h"]
    )

    values["reactor_temperature_c"] = clamp_sensor(
        "reactor_temperature_c",
        values["reactor_temperature_c"]
        + flow_delta * 0.035,
    )

    # Higher pump vibration increases bearing temperature.
    vibration_delta = max(
        0.0,
        values["pump_vibration_mm_s"]
        - BASELINE["pump_vibration_mm_s"],
    )

    values["bearing_temperature_c"] = clamp_sensor(
        "bearing_temperature_c",
        values["bearing_temperature_c"]
        + vibration_delta * 2.5,
    )

    # Pump degradation slightly lowers effective flow.
    if vibration_delta > 0.5:

        values["flow_rate_m3_h"] = clamp_sensor(
            "flow_rate_m3_h",
            values["flow_rate_m3_h"]
            - vibration_delta * 1.25,
        )''' 


    # Higher process load -> slightly more energy.
    process_load = (
        max(
            0.0,
            values["reactor_temperature_c"]
            - BASELINE["reactor_temperature_c"],
        )
        * 0.015
    )

    values["energy_consumption_mw"] = clamp_sensor(
        "energy_consumption_mw",
        values["energy_consumption_mw"]
        + process_load,
    )

    # Gas leak scenario affects H2S independently.
    values["h2s_ppm"] = clamp_sensor(
        "h2s_ppm",
        values["h2s_ppm"],
    )

    return values


def create_reading(
    *,
    rng: random.Random,
    sequence: int,
    plant: str,
    unit: str,
    asset_id: str,
    asset_type: str,
    equipment: str,
    source: str,
    scenario_offsets: Mapping[str, float],
    state_memory: Mapping[str, float] | None = None,
) -> SensorReading:

    values = generate_sensor_values(
        rng=rng,
        scenario_offsets=scenario_offsets,
        state_memory=state_memory,
    )

    return SensorReading(
        timestamp=utc_now_iso(),
        sequence=sequence,

        plant=plant,
        unit=unit,
        asset_id=asset_id,
        asset_type=asset_type,
        equipment=equipment,
        source=source,

        reactor_temperature_c=round(
            values["reactor_temperature_c"],
            2,
        ),
        reactor_pressure_bar=round(
            values["reactor_pressure_bar"],
            2,
        ),
        flow_rate_m3_h=round(
            values["flow_rate_m3_h"],
            2,
        ),
        feed_rate_t_h=round(
            values["feed_rate_t_h"],
            2,
        ),

        pump_vibration_mm_s=round(
            values["pump_vibration_mm_s"],
            3,
        ),
        bearing_temperature_c=round(
            values["bearing_temperature_c"],
            2,
        ),
        pump_rpm=round(
            values["pump_rpm"],
            1,
        ),

        energy_consumption_mw=round(
            values["energy_consumption_mw"],
            3,
        ),
        valve_position_pct=round(
            values["valve_position_pct"],
            2,
        ),
        level_pct=round(
            values["level_pct"],
            2,
        ),

        h2s_ppm=round(
            values["h2s_ppm"],
            3,
        ),
        so2_ppm=round(
            values["so2_ppm"],
            2,
        ),
        nox_ppm=round(
            values["nox_ppm"],
            2,
        ),
    )


def is_valid_reading(
    reading: SensorReading,
) -> bool:

    values = reading.to_dict()

    numeric_fields = [
        key
        for key, value in values.items()
        if isinstance(value, (int, float))
    ]

    return all(
        math.isfinite(
            float(values[key])
        )
        for key in numeric_fields
    )