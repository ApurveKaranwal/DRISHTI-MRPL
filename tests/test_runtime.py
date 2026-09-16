"""
Comprehensive automated tests for DRISHTI-MRPL Real-Time SCADA Runtime Telemetry & Risk Engine.
Validates all endpoints, authentic MRPL asset configurations, API 610 standards, and scenario transitions.
"""

import pytest
from fastapi.testclient import TestClient
from server import app
from runtime_data.runtime_api import simulator, start_runtime_simulator, stop_runtime_simulator


@pytest.fixture(scope="module")
def client():
    # Ensure simulator has at least 1 reading for tests
    start_runtime_simulator()
    simulator.generate_tick()  # Force 1 tick synchronously
    with TestClient(app) as test_client:
        yield test_client
    stop_runtime_simulator()


def test_runtime_refineries(client):
    """Verifies that the authentic MRPL Mangalore Refinery topology is served correctly."""
    response = client.get("/api/runtime/refineries")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["refineries"]) >= 1
    
    site = data["refineries"][0]
    assert "MRPL" in site["name"]
    assert "Mangalore" in site["name"]
    assert site["data_mode"] == "LIVE_SCADA_TELEMETRY"
    
    unit = site["units"][0]
    assert unit["id"] == "CDU-I"
    assert "P-101" in unit["assets"]
    assert "CDU-01" in unit["assets"]
    assert "HE-201" in unit["assets"]


def test_runtime_live_state(client):
    """Verifies the live plant state snapshot and risk engine assessment."""
    response = client.get("/api/runtime/live-state")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "site" in data
    assert "MRPL" in data["site"]["name"]
    assert "assets" in data
    assert len(data["assets"]) == 4
    
    # Check risk structure
    plant_risk = data["plant_risk"]
    assert "score" in plant_risk
    assert "status" in plant_risk
    assert 0 <= plant_risk["score"] <= 100
    assert plant_risk["status"] in ["NORMAL", "WATCH", "WARNING", "CRITICAL"]


def test_runtime_latest_record(client):
    """Verifies retrieval of the latest telemetry record with realistic bounds."""
    response = client.get("/api/runtime/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    reading = data["data"]["reading"]
    assert reading["plant"] == "MRPL-MANGALORE-REFINERY"
    assert reading["source"] == "MRPL_SCADA_OPC_GATEWAY"
    
    # Process sanity
    assert 250.0 <= reading["reactor_temperature_c"] <= 420.0
    assert 0.5 <= reading["reactor_pressure_bar"] <= 4.5
    assert 0.0 <= reading["pump_vibration_mm_s"] <= 12.0


def test_runtime_scenarios_list(client):
    """Verifies that all operational failure modes are registered."""
    response = client.get("/api/runtime/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    scenario_names = [s["name"] for s in data["scenarios"]]
    assert "NORMAL" in scenario_names
    assert "PUMP_DEGRADATION" in scenario_names
    assert "HIGH_TEMPERATURE" in scenario_names
    assert "PRESSURE_SURGE" in scenario_names
    assert "GAS_LEAK" in scenario_names
    assert "COOLING_FAILURE" in scenario_names
    assert "LOAD_INCREASE" in scenario_names


def test_runtime_scenario_trigger_and_reset(client):
    """Verifies setting a fault scenario and resetting back to normal."""
    # 1. Trigger Pump Degradation
    set_resp = client.post("/api/runtime/scenario", json={"scenario": "PUMP_DEGRADATION"})
    assert set_resp.status_code == 200
    set_data = set_resp.json()
    assert set_data["success"] is True
    assert set_data["scenario"]["name"] == "PUMP_DEGRADATION"
    
    # Force ticks to simulate degradation
    for _ in range(5):
        simulator.generate_tick()
        
    state_resp = client.get("/api/runtime/live-state")
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["scenario"]["name"] == "PUMP_DEGRADATION"
    
    # 2. Reset back to NORMAL
    reset_resp = client.post("/api/runtime/scenario", json={"scenario": "NORMAL"})
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data["success"] is True
    assert reset_data["scenario"]["name"] == "NORMAL"


def test_runtime_thresholds(client):
    """Verifies API 610 and OISD thresholds endpoint."""
    response = client.get("/api/runtime/thresholds")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    thresholds = data["thresholds"]
    assert "pump_vibration_mm_s" in thresholds
    assert "bearing_temperature_c" in thresholds
    assert "h2s_ppm" in thresholds
    
    vib_bands = thresholds["pump_vibration_mm_s"]
    assert vib_bands["CRITICAL"]["min_value"] == 7.1  # API 610 Trip limit
    assert vib_bands["HIGH_RISK"]["min_value"] == 4.5  # API 610 Alarm limit


def test_runtime_history(client):
    """Verifies time-series telemetry history retrieval."""
    response = client.get("/api/runtime/history?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert isinstance(data["data"], list)
