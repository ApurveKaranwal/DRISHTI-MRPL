"""
Explainable runtime risk engine.

Real-time industrial asset risk and anomaly detection engine calibrated against API Standard 610 (12th Edition) and OISD-STD-129.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .config import BASELINE, DEMO_THRESHOLDS
from .sensors import SensorReading


@dataclass(frozen=True)
class RiskAssessment:

    score: float

    status: str

    primary_risk: str

    recommendation: str

    alerts: list[str] = field(
        default_factory=list
    )

    contributors: list[dict[str, Any]] = field(
        default_factory=list
    )

    emergency: bool = False

    band_states: dict[str, str] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "status": self.status,
            "primary_risk": self.primary_risk,
            "recommendation": self.recommendation,
            "alerts": list(self.alerts),
            "contributors": list(
                self.contributors
            ),
            "emergency": self.emergency,
            "band_states": dict(
                self.band_states
            ),
        }


class RiskEngine:

    def __init__(
        self,
        *,
        trend_window: int = 8,
    ) -> None:

        self.trend_window = max(
            3,
            trend_window,
        )

    @staticmethod
    def _band_state(
        metric: str,
        value: float,
    ) -> str:

        bands = DEMO_THRESHOLDS.get(
            metric
        )

        if not bands:
            return "NORMAL"

        if (
            bands["CRITICAL"].min_value
            is not None
            and value
            >= bands["CRITICAL"].min_value
        ):
            return "CRITICAL"

        if (
            bands["HIGH_RISK"].min_value
            is not None
            and value
            >= bands["HIGH_RISK"].min_value
        ):

            return "HIGH_RISK"

        if (
            bands["WATCH"].min_value
            is not None
            and value
            >= bands["WATCH"].min_value
        ):

            return "WATCH"

        # Handle lower-is-worse measurements.
        normal = bands["NORMAL"]

        if (
            normal.min_value is not None
            and value < normal.min_value
        ):
            return "WATCH"

        return "NORMAL"

    def _trend(
        self,
        history: Sequence[
            SensorReading
        ],
        field: str,
    ) -> float:

        samples = list(
            history[
                -self.trend_window :
            ]
        )

        if len(samples) < 2:
            return 0.0

        first = float(
            getattr(
                samples[0],
                field,
            )
        )

        last = float(
            getattr(
                samples[-1],
                field,
            )
        )

        return (
            last - first
        ) / (
            len(samples) - 1
        )

    def assess(
        self,
        reading: SensorReading,
        history: Sequence[
            SensorReading
        ],
    ) -> RiskAssessment:

        points: list[
            tuple[
                str,
                float,
                str,
                str,
            ]
        ] = []

        alerts: list[str] = []

        band_states: dict[
            str,
            str,
        ] = {}

        # --------------------------------------------------
        # OPERATING BAND CHECKS
        # --------------------------------------------------

        monitored = [
            (
                "reactor_temperature_c",
                reading.reactor_temperature_c,
                "CDU Flash Zone Temp",
                355.0,
                368.0,
                385.0,
                "Regulate furnace coil outlet temperature and column reflux ratio.",
            ),
            (
                "reactor_pressure_bar",
                reading.reactor_pressure_bar,
                "Column Overhead Pressure",
                2.10,
                2.25,
                2.40,
                "Adjust overhead condenser fan pitch and monitor PSV-CDU-201 relief valve.",
            ),
            (
                "pump_vibration_mm_s",
                reading.pump_vibration_mm_s,
                "P-101A Vibration (API 610)",
                2.8,
                4.5,
                7.1,
                "API 610 Alert: Inspect bearing housing, mechanical seal flush, and shaft alignment.",
            ),
            (
                "bearing_temperature_c",
                reading.bearing_temperature_c,
                "P-101A Bearing Temp (API 610)",
                72.0,
                82.0,
                93.0,
                "API 610 Bearing Alert: Check lube oil circulation, cooler delta-P, and bearing clearance.",
            ),
            (
                "energy_consumption_mw",
                reading.energy_consumption_mw,
                "Motor Power Consumption",
                4.2,
                4.8,
                5.5,
                "Review electrical motor thermal protection and pump hydraulic load.",
            ),
            (
                "h2s_ppm",
                reading.h2s_ppm,
                "Atmospheric H2S (OISD-129)",
                5.0,
                10.0,
                15.0,
                "OISD-STD-129 Alert: Toxic gas alarm breached; execute seal flush isolation and muster.",
            ),
        ]

        for (
            metric,
            value,
            label,
            watch,
            high,
            critical,
            recommendation,
        ) in monitored:

            state = self._band_state(
                metric,
                value,
            )

            band_states[
                metric
            ] = state

            if state == "WATCH":

                points.append(
                    (
                        metric,
                        8.0,
                        f"{label} is elevated",
                        recommendation,
                    )
                )

            elif state == "HIGH_RISK":

                points.append(
                    (
                        metric,
                        18.0,
                        f"{label} is in the high-risk demonstration band",
                        recommendation,
                    )
                )

                alerts.append(
                    f"{label} has entered the "
                    "high-risk demonstration band."
                )

            elif state == "CRITICAL":

                points.append(
                    (
                        metric,
                        35.0,
                        f"{label} is in the critical demonstration band",
                        recommendation,
                    )
                )

                alerts.append(
                    f"CRITICAL: {label} "
                    "crossed the demonstration threshold."
                )

        # --------------------------------------------------
        # TREND ANALYSIS
        # --------------------------------------------------

        trend_metrics = [
            (
                "reactor_temperature_c",
                reading.reactor_temperature_c,
                0.70,
                12.0,
                "Temperature is rising steadily",
                "Inspect cooling/process response.",
            ),
            (
                "reactor_pressure_bar",
                reading.reactor_pressure_bar,
                0.22,
                12.0,
                "Pressure is rising steadily",
                "Review pressure-control response.",
            ),
            (
                "pump_vibration_mm_s",
                reading.pump_vibration_mm_s,
                0.07,
                18.0,
                "Pump vibration is trending upward",
                "Inspect pump/bearing condition.",
            ),
            (
                "bearing_temperature_c",
                reading.bearing_temperature_c,
                0.30,
                14.0,
                "Bearing temperature is trending upward",
                "Review lubrication and mechanical condition.",
            ),
            (
                "energy_consumption_mw",
                reading.energy_consumption_mw,
                0.05,
                8.0,
                "Energy consumption is trending upward",
                "Check process loading and equipment efficiency.",
            ),
        ]

        for (
            field,
            _value,
            threshold,
            maximum_points,
            reason,
            recommendation,
        ) in trend_metrics:

            trend = self._trend(
                history,
                field,
            )

            if trend > threshold:

                contribution = min(
                    maximum_points,
                    (
                        trend
                        / threshold
                    )
                    * maximum_points,
                )

                points.append(
                    (
                        f"{field}_trend",
                        contribution,
                        reason,
                        recommendation,
                    )
                )

                alerts.append(
                    f"{reason}."
                )

        # --------------------------------------------------
        # CROSS-SENSOR CORRELATION
        # --------------------------------------------------

        if (
            reading.pump_vibration_mm_s
            > 2.4
            and reading.bearing_temperature_c
            > 70.0
        ):

            points.append(
                (
                    "mechanical_correlation",
                    15.0,
                    (
                        "Pump vibration and "
                        "bearing temperature are "
                        "rising together"
                    ),
                    (
                        "Prioritize mechanical "
                        "inspection of the pump."
                    ),
                )
            )

        if (
            reading.reactor_temperature_c
            > 350.0
            and reading.reactor_pressure_bar
            > 44.0
        ):

            points.append(
                (
                    "process_correlation",
                    14.0,
                    (
                        "Temperature and pressure "
                        "are elevated together"
                    ),
                    (
                        "Review process-control "
                        "response and cooling."
                    ),
                )
            )

        if (
            reading.feed_rate_t_h
            > 123.0
            and reading.energy_consumption_mw
            > 9.0
        ):

            points.append(
                (
                    "load_correlation",
                    8.0,
                    (
                        "Feed rate and energy "
                        "consumption are both elevated"
                    ),
                    (
                        "Review process loading."
                    ),
                )
            )

        # --------------------------------------------------
        # EMERGENCY CONDITIONS
        # --------------------------------------------------

        emergency = (
            reading.h2s_ppm >= 15.0
            or reading.reactor_pressure_bar >= 55.0
            or reading.reactor_temperature_c >= 390.0
            or reading.pump_vibration_mm_s >= 4.5
            or reading.bearing_temperature_c >= 80.0
        )

        if emergency:

            alerts.insert(
                0,
                (
                    "CRITICAL: simulated emergency "
                    "condition detected. This is a "
                    "demonstration system, not a real "
                    "safety instrument."
                ),
            )

        score = sum(
            max(
                0.0,
                contribution,
            )
            for (
                _signal,
                contribution,
                _reason,
                _recommendation,
            )
            in points
        )

        if emergency:
            score += 15.0

        score = round(
            min(
                100.0,
                max(
                    0.0,
                    score,
                ),
            ),
            1,
        )

        if emergency or score >= 80.0:

            status = "CRITICAL"

        elif score >= 60.0:

            status = "WARNING"

        elif score >= 30.0:

            status = "WATCH"

        else:

            status = "NORMAL"

        # --------------------------------------------------
        # PRIMARY RISK
        # --------------------------------------------------

        if points:

            top = max(
                points,
                key=lambda item: item[1],
            )

            primary_risk = top[2]

            recommendation = top[3]

        else:

            primary_risk = (
                "No significant anomaly detected"
            )

            recommendation = (
                "Continue monitoring live telemetry "
                "and trend changes."
            )

        # --------------------------------------------------
        # TOP CONTRIBUTORS
        # --------------------------------------------------

        sorted_points = sorted(
            points,
            key=lambda item: item[1],
            reverse=True,
        )

        contributors = [

            {
                "signal": signal,
                "contribution": round(
                    contribution,
                    1,
                ),
                "reason": reason,
            }

            for (
                signal,
                contribution,
                reason,
                _recommendation,
            )
            in sorted_points[:8]
        ]

        return RiskAssessment(
            score=score,
            status=status,
            primary_risk=primary_risk,
            recommendation=recommendation,
            alerts=alerts[:8],
            contributors=contributors,
            emergency=emergency,
            band_states=band_states,
        )