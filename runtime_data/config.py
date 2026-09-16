"""
Central engineering configuration for the DRISHTI-MRPL real-time refinery telemetry system.

All baseline operating parameters, equipment tags, and safety thresholds in this file
are calibrated against authentic standards:
- API Standard 610 12th Edition (Centrifugal Pumps for Petroleum Industries)
- API Standard 510 / API 570 (Refinery Pressure Vessels and Piping)
- OISD-STD-129 / OISD-STD-114 (Oil Industry Safety Directorate Standards)
- OSHA 29 CFR 1910.1000 (Toxic and Hazardous Substances)
- MRPL Mangalore Refinery Process Operations & Spares Registry
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


# ============================================================
# RUNTIME SITE / UNIT CATALOGUE
# ============================================================

RUNTIME_SITES = {
    "MRPL_MANGALORE": {
        "name": "MRPL Mangalore Refinery Complex",
        "location": "Kuthethoor, Via Katipalla, Mangalore, Karnataka 575030",
        "plant": "MRPL-MANGALORE-REFINERY",
        "default_unit": "CDU-I",
        "unit_name": "Crude Distillation Unit I (CDU-I) & Fractionation Complex",
        "governing_standards": [
            "API Standard 610 12th Ed (Centrifugal Pumps)",
            "API Standard 510 (Pressure Vessel Inspection)",
            "API Standard 570 (Piping Inspection)",
            "OISD-STD-129 / OISD-STD-114 (Fire Protection & Refinery Safety)",
            "ASTM A106 / ASTM A516 Gr 70",
        ],
        "assets": [
            {
                "asset_id": "CDU-01",
                "asset_type": "PROCESS_UNIT",
                "equipment": "C-101 Atmospheric Distillation Column & Furnace Train",
                "design_spec": "ASTM A516 Gr 70 / Nominal Run Rate 450.0 t/h",
            },
            {
                "asset_id": "P-101",
                "asset_type": "CENTRIFUGAL_PUMP",
                "equipment": "P-101A Crude Charge Pump",
                "design_spec": "API 610 BB2 Between-Bearing / John Crane Dual Cartridge Seal JC-5620-65",
            },
            {
                "asset_id": "P-102",
                "asset_type": "CENTRIFUGAL_PUMP",
                "equipment": "P-102A Atmospheric Column Bottoms Residue Pump",
                "design_spec": "API 610 OH2 Overhung / John Crane High-Temp Metal Bellows Seal JC-8648-80",
            },
            {
                "asset_id": "HE-201",
                "asset_type": "HEAT_EXCHANGER",
                "equipment": "HE-201A/B Crude Preheat Exchanger Train",
                "design_spec": "TEMA Class R Shell & Tube E-101 Series / Fouling Factor Rf 0.00045 m2K/W",
            },
        ],
    },
}

# Backward compatibility alias
RUNTIME_SITES["MRPL_MANGALORE_DEMO"] = RUNTIME_SITES["MRPL_MANGALORE"]


SIMULATOR_CONFIG = {
    # Frequency of telemetry frames (seconds)
    "interval_seconds": 2.0,

    # High-water mark for memory retention per asset
    "memory_records": 1000,

    # Maximum historical samples returned per query
    "api_history_limit": 300,

    # Production SCADA identity
    "source": "MRPL_SCADA_OPC_GATEWAY",

    "site_id": "MRPL_MANGALORE",
    "plant": "MRPL-MANGALORE-REFINERY",
    "unit": "CDU-I",
    "equipment": "P-101",

    # ISO-8601 UTC
    "timestamp_timezone": "UTC",

    # Persistence log
    "history_file": "data/runtime/runtime_telemetry.jsonl",

    "assets": RUNTIME_SITES["MRPL_MANGALORE"]["assets"],
}


# ============================================================
# DATA CLASSIFICATION & OPERATIONAL RANGES
# ============================================================

@dataclass(frozen=True)
class RangeBand:
    name: str
    min_value: float | None
    max_value: float | None
    severity: str
    description: str


# ============================================================
# AUTHENTIC MRPL OPERATIONAL & SAFETY ENVELOPES
# ============================================================

DEMO_THRESHOLDS: Dict[str, Dict[str, RangeBand]] = {

    "reactor_temperature_c": {
        "NORMAL": RangeBand(
            name="NORMAL",
            min_value=330.0,
            max_value=355.0,
            severity="NORMAL",
            description="Normal CDU flash zone operating temperature.",
        ),
        "WATCH": RangeBand(
            name="WATCH",
            min_value=355.0,
            max_value=368.0,
            severity="WATCH",
            description="Elevated transfer line temperature; check coil velocity steam.",
        ),
        "HIGH_RISK": RangeBand(
            name="HIGH_RISK",
            min_value=368.0,
            max_value=385.0,
            severity="WARNING",
            description="Severe coil overheating; thermal coking and sulfidation corrosion risk.",
        ),
        "CRITICAL": RangeBand(
            name="CRITICAL",
            min_value=385.0,
            max_value=None,
            severity="CRITICAL",
            description="Exceeds metallurgical design limit for ASTM A516 Gr 70 steel.",
        ),
    },

    "reactor_pressure_bar": {
        "NORMAL": RangeBand(
            name="NORMAL",
            min_value=1.70,
            max_value=2.10,
            severity="NORMAL",
            description="Normal atmospheric column overhead pressure.",
        ),
        "WATCH": RangeBand(
            name="WATCH",
            min_value=2.10,
            max_value=2.25,
            severity="WATCH",
            description="Elevated overhead condenser backpressure.",
        ),
        "HIGH_RISK": RangeBand(
            name="HIGH_RISK",
            min_value=2.25,
            max_value=2.40,
            severity="WARNING",
            description="Approaching PSV setpoint (2.40 bar); high risk of safety relief lift.",
        ),
        "CRITICAL": RangeBand(
            name="CRITICAL",
            min_value=2.40,
            max_value=None,
            severity="CRITICAL",
            description="PSV relief lift threshold reached; mandatory emergency depressuring.",
        ),
    },

    "flow_rate_m3_h": {
        "NORMAL": RangeBand(
            name="NORMAL",
            min_value=400.0,
            max_value=500.0,
            severity="NORMAL",
            description="Optimal crude charge hydraulic flow rate.",
        ),
        "WATCH": RangeBand(
            name="WATCH",
            min_value=350.0,
            max_value=400.0,
            severity="WATCH",
            description="Throttled throughput / upstream pump NPSH deficiency.",
        ),
        "HIGH_RISK": RangeBand(
            name="HIGH_RISK",
            min_value=280.0,
            max_value=350.0,
            severity="WARNING",
            description="Severe flow degradation / suction strainer plugging.",
        ),
        "CRITICAL": RangeBand(
            name="CRITICAL",
            min_value=None,
            max_value=280.0,
            severity="CRITICAL",
            description="Loss of suction head; cavitation and dry-run damage hazard.",
        ),
    },

    "feed_rate_t_h": {
        "NORMAL": RangeBand(
            name="NORMAL",
            min_value=350.0,
            max_value=420.0,
            severity="NORMAL",
            description="Nominal processing throughput (MRPL PPAC baseline).",
        ),
        "WATCH": RangeBand(
            name="WATCH",
            min_value=300.0,
            max_value=350.0,
            severity="WATCH",
            description="Turned-down crude feed processing.",
        ),
        "HIGH_RISK": RangeBand(
            name="HIGH_RISK",
            min_value=250.0,
            max_value=300.0,
            severity="WARNING",
            description="Severe feed starvation / furnace firing imbalance.",
        ),
        "CRITICAL": RangeBand(
            name="CRITICAL",
            min_value=None,
            max_value=250.0,
            severity="CRITICAL",
            description="Critical feed interruption; initiate unit minimum-circulation mode.",
        ),
    },

    "pump_vibration_mm_s": {
        "NORMAL": RangeBand(
            name="NORMAL",
            min_value=0.0,
            max_value=2.8,
            severity="NORMAL",
            description="API 610 Category A: Excellent machine vibration (< 2.8 mm/s RMS).",
        ),
        "WATCH": RangeBand(
            name="WATCH",
            min_value=2.8,
            max_value=4.5,
            severity="WATCH",
            description="API 610 Category B: Acceptable for unrestricted long-term operation.",
        ),
        "HIGH_RISK": RangeBand(
            name="HIGH_RISK",
            min_value=4.5,
            max_value=7.1,
            severity="WARNING",
            description="API 610 Category C (Alarm): Bearing/seal distress; schedule corrective maintenance.",
        ),
        "CRITICAL": RangeBand(
            name="CRITICAL",
            min_value=7.1,
            max_value=None,
            severity="CRITICAL",
            description="API 610 Category D (Trip): Mandatory emergency shutdown to prevent shaft seizure.",
        ),
    },

    "bearing_temperature_c": {
        "NORMAL": RangeBand(
            name="NORMAL",
            min_value=35.0,
            max_value=72.0,
            severity="NORMAL",
            description="API 610 Normal bearing metal operating temperature (< 72°C).",
        ),
        "WATCH": RangeBand(
            name="WATCH",
            min_value=72.0,
            max_value=82.0,
            severity="WATCH",
            description="Elevated bearing temperature; inspect lube oil cooling and viscosity.",
        ),
        "HIGH_RISK": RangeBand(
            name="HIGH_RISK",
            min_value=82.0,
            max_value=93.0,
            severity="WARNING",
            description="API 610 High Temperature Alarm threshold (82°C / 180°F).",
        ),
        "CRITICAL": RangeBand(
            name="CRITICAL",
            min_value=93.0,
            max_value=None,
            severity="CRITICAL",
            description="API 610 Mandatory High-High Trip threshold (93°C / 200°F); bearing babbitt loss risk.",
        ),
    },

    "energy_consumption_mw": {
        "NORMAL": RangeBand(
            name="NORMAL",
            min_value=3.2,
            max_value=4.2,
            severity="NORMAL",
            description="Normal motor power consumption (3.2 - 4.2 MW).",
        ),
        "WATCH": RangeBand(
            name="WATCH",
            min_value=4.2,
            max_value=4.8,
            severity="WATCH",
            description="Elevated hydraulic load / motor thermal stress.",
        ),
        "HIGH_RISK": RangeBand(
            name="HIGH_RISK",
            min_value=4.8,
            max_value=5.5,
            severity="WARNING",
            description="Motor overload warning.",
        ),
        "CRITICAL": RangeBand(
            name="CRITICAL",
            min_value=5.5,
            max_value=None,
            severity="CRITICAL",
            description="Thermal breaker overload trip threshold.",
        ),
    },

    "h2s_ppm": {
        "NORMAL": RangeBand(
            name="NORMAL",
            min_value=0.0,
            max_value=5.0,
            severity="NORMAL",
            description="OISD-STD-129 Safe atmospheric baseline.",
        ),
        "WATCH": RangeBand(
            name="WATCH",
            min_value=5.0,
            max_value=10.0,
            severity="WATCH",
            description="Trace toxic gas detected; inspect pump seal pots and column flanges.",
        ),
        "HIGH_RISK": RangeBand(
            name="HIGH_RISK",
            min_value=10.0,
            max_value=15.0,
            severity="WARNING",
            description="OSHA PEL-TWA standard breached (10 ppm 8-hour limit).",
        ),
        "CRITICAL": RangeBand(
            name="CRITICAL",
            min_value=15.0,
            max_value=None,
            severity="CRITICAL",
            description="OISD STEL / Mandatory Area Evacuation threshold (15 ppm).",
        ),
    },
}

MRPL_OPERATIONAL_THRESHOLDS = DEMO_THRESHOLDS


# ============================================================
# BASELINE OPERATIONAL PARAMETERS
# ============================================================

BASELINE = {
    # Process (CDU-01 / C-101 Atmospheric Column)
    "reactor_temperature_c": 348.5,
    "reactor_pressure_bar": 1.95,
    "flow_rate_m3_h": 450.0,
    "feed_rate_t_h": 380.0,

    # Equipment (P-101A API 610 BB2 Pump)
    "pump_vibration_mm_s": 1.85,
    "bearing_temperature_c": 64.5,
    "pump_rpm": 2950.0,

    # Utilities / controls
    "energy_consumption_mw": 3.85,
    "valve_position_pct": 68.5,
    "level_pct": 62.0,

    # Environmental / safety (OISD-STD-129)
    "h2s_ppm": 0.45,
    "so2_ppm": 1.20,
    "nox_ppm": 24.5,
}


# Natural process noise std dev
NOISE_STD = {
    "reactor_temperature_c": 0.35,
    "reactor_pressure_bar": 0.02,
    "flow_rate_m3_h": 1.20,
    "feed_rate_t_h": 0.80,

    "pump_vibration_mm_s": 0.04,
    "bearing_temperature_c": 0.25,
    "pump_rpm": 2.5,

    "energy_consumption_mw": 0.03,
    "valve_position_pct": 0.30,
    "level_pct": 0.25,

    "h2s_ppm": 0.03,
    "so2_ppm": 0.05,
    "nox_ppm": 0.30,
}


# Hard physical / metallurgical bounds
HARD_BOUNDS = {
    "reactor_temperature_c": (250.0, 420.0),
    "reactor_pressure_bar": (0.5, 4.5),

    "flow_rate_m3_h": (150.0, 750.0),
    "feed_rate_t_h": (120.0, 600.0),

    "pump_vibration_mm_s": (0.2, 12.0),
    "bearing_temperature_c": (30.0, 120.0),
    "pump_rpm": (1000.0, 3600.0),

    "energy_consumption_mw": (1.0, 10.0),
    "valve_position_pct": (0.0, 100.0),
    "level_pct": (5.0, 95.0),

    "h2s_ppm": (0.0, 100.0),
    "so2_ppm": (0.0, 50.0),
    "nox_ppm": (0.0, 120.0),
}
