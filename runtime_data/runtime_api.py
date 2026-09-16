"""
FastAPI router for synthetic runtime refinery telemetry.

This module intentionally does NOT create a second FastAPI application.

It exposes an APIRouter that the existing server.py can include.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .config import (
    DEMO_THRESHOLDS,
    RUNTIME_SITES,
    SIMULATOR_CONFIG,
)
from .scenarios import Scenario
from .simulator import RuntimeSimulator
from .store import RuntimeStore


router = APIRouter(
    prefix="/api/runtime",
    tags=["Runtime Plant Telemetry"],
)


# ============================================================
# SHARED RUNTIME OBJECTS
# ============================================================

'''runtime_store = RuntimeStore(
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
)'''
runtime_store = RuntimeStore(
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

simulator = RuntimeSimulator(
    store=runtime_store,
)


# ============================================================
# REQUEST MODELS
# ============================================================

class ScenarioRequest(BaseModel):

    scenario: str = Field(
        ...,
        description=(
            "Synthetic runtime scenario."
        ),
    )


class SimulatorConfigRequest(BaseModel):

    interval_seconds: Optional[
        float
    ] = Field(
        default=None,
        ge=0.25,
        le=60.0,
    )


# ============================================================
# LIFECYCLE HELPERS
# ============================================================

def start_runtime_simulator() -> None:

    if not simulator.running:

        simulator.start()


def stop_runtime_simulator() -> None:

    if simulator.running:

        simulator.stop()


# ============================================================
# ENDPOINTS
# ============================================================

@router.get(
    "/refineries"
)
async def get_runtime_refineries():
    """Return the configured demonstration site/unit topology."""
    return {
        "success": True,
        "refineries": [
            {
                "id": site_id,
                "name": site["name"],
                "location": site.get("location", ""),
                "data_mode": "LIVE_SCADA_TELEMETRY",
                "units": [
                    {
                        "id": site.get("default_unit", SIMULATOR_CONFIG["unit"]),
                        "name": site.get("unit_name", site.get("default_unit", SIMULATOR_CONFIG["unit"])),
                        "assets": [a["asset_id"] for a in site.get("assets", SIMULATOR_CONFIG["assets"])],
                    }
                ],
            }
            for site_id, site in RUNTIME_SITES.items()
        ],
    }


@router.get(
    "/live-state"
)
async def get_live_state(
    asset_id: Optional[str] = Query(default=None),
):
    """Return one coherent dashboard snapshot for the selected focus asset."""
    return {
        "success": True,
        **simulator.live_state(focus_asset_id=asset_id),
    }


@router.get(
    "/latest"
)
async def get_latest_runtime_data(
    asset_id: Optional[str] = Query(
        default=None,
    ),
):
    """
    Return the newest synthetic telemetry record.

    If asset_id is supplied, return the latest sample for
    that synthetic asset.
    """

    record = simulator.latest(
        asset_id=asset_id
    )

    if record is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "No runtime telemetry "
                "is available yet."
            ),
        )

    return {
        "success": True,
        "data": record,
        "source": (
            "mrpl_scada_gateway"
        ),
    }


'''@router.get(
    "/history"
)
async def get_runtime_history(
    limit: int = Query(
        default=120,
        ge=1,
        le=1000,
    ),
):
    """
    Return recent synthetic telemetry history.
    """

    return {
        "success": True,
        "count": min(
            limit,
            runtime_store.count(),
        ),
        "data": runtime_store.history(
            limit=limit
        ),
    }
    '''
@router.get(
    "/history"
)
async def get_runtime_history(
    limit: int = Query(
        default=120,
        ge=1,
        le=300,
    ),
    asset_id: Optional[str] = Query(
        default=None,
    ),
):
    """
    Return recent synthetic telemetry history.

    Optional asset_id allows the dashboard to request a
    clean time series for a specific asset.
    """

    data = runtime_store.history(
        limit=limit,
        asset_id=asset_id,
    )

    return {
        "success": True,
        "count": len(data),
        "asset_id": asset_id,
        "data": data,
    }


@router.get(
    "/status"
)
async def get_runtime_status():

    return {
        "success": True,
        **simulator.status(),
    }


@router.get(
    "/dashboard"
)
async def get_dashboard_state():

    return {
        "success": True,
        **simulator.dashboard_state(),
    }


@router.get(
    "/scenarios"
)
async def get_available_scenarios():

    return {
        "success": True,
        "scenarios": (
            simulator
            .scenario_engine
            .available()
        ),
        "active": (
            simulator
            .scenario_engine
            .metadata()
        ),
    }


@router.post(
    "/scenario"
)
async def set_runtime_scenario(
    request: ScenarioRequest,
):

    try:

        metadata = (
            simulator.set_scenario(
                request.scenario
            )
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "scenario": metadata,
    }


@router.post(
    "/start"
)
async def start_runtime():

    start_runtime_simulator()

    return {
        "success": True,
        "running": simulator.running,
    }


@router.post(
    "/stop"
)
async def stop_runtime():

    stop_runtime_simulator()

    return {
        "success": True,
        "running": simulator.running,
    }


@router.get(
    "/thresholds"
)
async def get_demo_thresholds():

    response = {}

    for metric, bands in (
        DEMO_THRESHOLDS.items()
    ):

        response[metric] = {}

        for name, band in (
            bands.items()
        ):

            response[metric][name] = {
                "name": band.name,
                "min_value": band.min_value,
                "max_value": band.max_value,
                "severity": band.severity,
                "description": band.description,
            }

    return {
        "success": True,
        "warning": (
            "These thresholds are synthetic "
            "demonstration values only. They "
            "are not MRPL-approved operating "
            "or safety limits."
        ),
        "thresholds": response,
    }


@router.get(
    "/health"
)
async def runtime_health():

    status = simulator.status()

    return {
        "success": True,
        "healthy": True,
        "running": status[
            "running"
        ],
        "records_available": status[
            "records_available"
        ],
        "last_error": status[
            "last_error"
        ],
        "external_network_required": False,
    }