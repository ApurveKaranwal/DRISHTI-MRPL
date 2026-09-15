import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from server import app
from model_router import get_model_router, REGISTRY_PATH

client = TestClient(app)

def test_static_assets_contain_features():
    """Verify HTML, CSS, and JS include all components for Features 1, 2, 3, 4."""
    html_path = Path("static/index.html")
    css_path = Path("static/app.css")
    js_path = Path("static/app.js")

    assert html_path.exists()
    assert css_path.exists()
    assert js_path.exists()

    html_content = html_path.read_text(encoding="utf-8")
    assert "modal-register-model" in html_content, "Feature 3 Register Modal missing in HTML"
    assert "modal-file-preview" in html_content, "Feature 4 Preview Modal missing in HTML"
    assert "btn-scan-models" in html_content, "Manual scan button missing in HTML"
    assert "openRegisterModelModal" not in html_content, "Manual register modal trigger should be removed per user request"

    css_content = css_path.read_text(encoding="utf-8")
    assert ".execution-stream-card" in css_content, "Feature 1 execution card CSS missing"
    assert ".step-item.active" in css_content, "Feature 1 active animation CSS missing"
    assert ".model-routing-badge-wrap" in css_content, "Feature 2 badge CSS missing"
    assert ".deliverable-card-rich" in css_content, "Feature 4 rich card CSS missing"
    assert ".btn-card-preview" in css_content, "Feature 4 preview button CSS missing"
    assert ".preview-slides-grid" in css_content, "Feature 4 PPTX preview CSS missing"

    js_content = js_path.read_text(encoding="utf-8")
    assert "/api/chat/stream" in js_content, "Feature 1 streaming endpoint missing in JS"
    assert "openFilePreview" in js_content, "Feature 4 openFilePreview missing in JS"
    assert "renderPreviewContent" in js_content, "Feature 4 preview renderer missing in JS"
    assert "submitRegisterModel" in js_content, "Feature 3 register model submit missing in JS"


def test_preview_endpoint_security_traversal():
    """Verify directory traversal is blocked by /api/preview."""
    res = client.get("/api/preview/../../secret.txt")
    assert res.status_code in (403, 404), "Directory traversal should return 403 or 404"


def test_preview_endpoint_data_csv():
    """Verify /api/preview for CSV returns tabular rows."""
    res = client.get("/api/preview/real_crude_oil_assays.csv?source=data")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "csv"
    assert "rows" in data
    assert len(data["rows"]) > 0
    headers = data["rows"][0]
    assert "crude_name" in headers or "origin_country" in headers


def test_preview_endpoint_data_pdf():
    """Verify /api/preview for PDF returns download url."""
    res = client.get("/api/preview/real_cdu_ultrasonic_thickness_scan.pdf?source=data")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "pdf"
    assert "url" in data


def test_preview_endpoint_reports_pptx():
    """Verify /api/preview for PPTX presentation returns slide cards and bullets."""
    pptx_files = list(Path("outputs/reports").glob("*.pptx"))
    if not pptx_files:
        pytest.skip("No PPTX reports generated yet to preview.")
    fname = pptx_files[0].name
    res = client.get(f"/api/preview/{fname}?source=reports")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "pptx"
    assert "slides" in data
    assert len(data["slides"]) > 0
    first_slide = data["slides"][0]
    assert "slide_number" in first_slide
    assert "title" in first_slide


def test_preview_endpoint_reports_docx():
    """Verify /api/preview for DOCX document returns structured paragraphs and tables."""
    docx_files = list(Path("outputs/reports").glob("*.docx"))
    if not docx_files:
        pytest.skip("No DOCX reports generated yet to preview.")
    fname = docx_files[0].name
    res = client.get(f"/api/preview/{fname}?source=reports")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "docx"
    assert "paragraphs" in data
    assert len(data["paragraphs"]) > 0



def test_chat_streaming_ndjson():
    """Verify /api/chat/stream returns NDJSON events including routing, step_start, step_complete, complete."""
    payload = {
        "message": "Analyze PPAC monthly crude throughput and capacity utilization for MRPL",
        "files": ["data/ppac_mrpl_monthly_crude_processing.csv"],
        "history": []
    }
    response = client.post("/api/chat/stream", json=payload)
    assert response.status_code == 200
    event_types = []
    complete_event = None
    for line in response.text.strip().split("\n"):
        if not line:
            continue
        event = json.loads(line)
        event_types.append(event.get("type"))
        if event.get("type") == "complete":
            complete_event = event

    assert "routing" in event_types, f"Expected 'routing' event, got: {event_types}"
    assert "plan" in event_types, f"Expected 'plan' event, got: {event_types}"
    assert "step_start" in event_types, f"Expected 'step_start' event, got: {event_types}"
    assert "step_complete" in event_types, f"Expected 'step_complete' event, got: {event_types}"
    assert "complete" in event_types, f"Expected 'complete' event, got: {event_types}"

    assert complete_event is not None
    assert complete_event.get("success") is True
    assert "answer" in complete_event
    assert "execution_trace" in complete_event
    trace = complete_event["execution_trace"]
    assert len(trace) > 0
    first_step = trace[0]
    assert "worker" in first_step
    assert "worker_name" in first_step
    assert "duration_ms" in first_step
    assert "summary" in first_step
    assert "status" in first_step


def test_model_registration_and_cleanup():
    """Verify /api/models/register dynamically registers an open-weight model and cleans up."""
    router = get_model_router()
    test_model_id = "test-custom-qwen:1.8b"

    payload = {
        "model_id": test_model_id,
        "roles": ["analyst", "coder"],
        "capabilities": ["reasoning", "sql_generation"],
        "description": "Integration test model",
        "vram_estimate_gb": 1.8,
        "context_window": 4096,
        "temperature": 0.1,
        "set_as_active": False
    }

    try:
        res = client.post("/api/models/register", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"

        # Verify model appears in router profiles
        res_models = client.get("/api/models")
        assert res_models.status_code == 200
        models_data = res_models.json()
        all_ids = [m["model_id"] for p in models_data["profiles"] for m in p.get("available_models", [])]
        assert test_model_id in all_ids, f"{test_model_id} not found in {all_ids}"
    finally:
        # Cleanup
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            registry = json.load(f)
        if test_model_id in registry.get("models", {}):
            del registry["models"][test_model_id]
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)


def test_settings_redesign_and_auto_detect_assets():
    """Verify HTML, CSS, and JS include all components for Settings Redesign and 10-Min Autonomous Detection."""
    html_content = Path("static/index.html").read_text(encoding="utf-8")
    assert "settings-control-strip" in html_content
    assert "auto-scan-countdown" in html_content
    assert "btn-scan-models" in html_content
    assert "discovered-models-banner" in html_content
    assert "settings-cards-stack" in html_content
    assert "settings-hardware-specs" not in html_content
    assert "Compute Hardware Budget & Local Engine" not in html_content


    css_content = Path("static/app.css").read_text(encoding="utf-8")
    assert ".settings-control-strip" in css_content
    assert ".auto-scan-status-wrap" in css_content
    assert ".model-role-card" in css_content
    assert ".model-role-description" in css_content
    assert ".hw-metric-grid-4col" in css_content
    assert ".discovered-models-banner" in css_content

    js_content = Path("static/app.js").read_text(encoding="utf-8")
    assert "initAutonomousModelDetection" in js_content
    assert "autoDetectSecondsRemaining" in js_content
    assert "discoverModels" in js_content
    assert "renderDiscoveredModelsBanner" in js_content
    assert "quickConfirmDiscoveredModel" in js_content


def test_models_discover_endpoint():
    """Verify /api/models/discover endpoint functions properly and returns expected structure."""
    res = client.get("/api/models/discover")
    assert res.status_code == 200
    data = res.json()
    assert "pending" in data
    assert "count" in data
    assert isinstance(data["pending"], list)
    assert data["count"] == len(data["pending"])

    # Test dismissing a fake/dummy model
    dismiss_res = client.post("/api/models/dismiss", json={"model_id": "nonexistent-test-model:1b"})
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["status"] == "success"


def test_airgap_active_socket_enforcement():
    """Verify that SovereignNetworkAuditor actively blocks outbound WAN socket connections."""
    import socket
    from server import auditor

    auditor.enable_airgap_enforcement()
    assert auditor._enforcement_active is True

    # 1. External WAN connection attempt must be actively blocked
    blocked = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 53))
        s.close()
    except PermissionError as pe:
        blocked = True
        assert "Air-Gap" in str(pe)
    except Exception:
        pass
    assert blocked, "Active enforcer must intercept and block external WAN connect with PermissionError"

    # 2. Verify blocked event was logged
    blocked_events = [e for e in auditor.event_log if e.event_type == "AIRGAP_EGRESS_BLOCKED"]
    assert len(blocked_events) > 0, "Blocked egress must be recorded in auditor event log"

    # 3. Telemetry reflects enforcement
    telem = auditor.get_telemetry()
    assert telem["airgap_enforcement"] == "ACTIVE"
    assert telem["blocked_breaches_count"] >= 1


def test_persistent_hash_chained_audit_trail():
    """Verify /api/audit-trail returns sequential SHA-256 hash-chained session ledger."""
    res = client.get("/api/audit-trail")
    assert res.status_code == 200
    data = res.json()
    assert "records" in data
    assert "session_id" in data
    assert "latest_chain_hash" in data
    assert len(data["records"]) > 0

    # Verify sequential hash integrity
    prev_hash = "0" * 64
    for entry in data["records"]:
        assert entry["prev_hash"] == prev_hash
        assert len(entry["entry_hash"]) == 64
        prev_hash = entry["entry_hash"]


def test_hydraulic_scenario_simulator_api_and_ui():
    """Verify Darcy-Weisbach simulator API calculations and UI components."""
    # API Verification
    res = client.post(
        "/api/simulate-scenario",
        json={
            "pipeline_flow_m3_h": 600.0,
            "pipeline_length_m": 800.0,
            "throughput_delta_pct": 5.0,
        },
    )
    assert res.status_code == 200
    sim = res.json()["simulated"]
    assert sim["pressure_drop_bar"] > 0
    assert sim["pipeline_velocity_m_s"] > 0
    assert sim["reynolds_number"] > 2000
    assert sim["throughput_mmt"] > 16.774

    # UI Verification
    html = Path("static/index.html").read_text(encoding="utf-8")
    assert "sim-flow-rate" in html
    assert "sim-line-length" in html
    assert "sim-throughput-delta" in html
    assert "sim-dp-val" in html
    assert "btn-run-simulation" in html
    assert "docs-search-input" in html
    assert "deliverables-search-input" in html

    js = Path("static/app.js").read_text(encoding="utf-8")
    assert "runHydraulicSimulation" in js
    assert "filterDocuments" in js
    assert "filterDeliverables" in js
    assert "downloadAuditTrailJsonl" in js


def test_multi_turn_chat_history():
    """Verify /api/chat accepts conversation history without error."""
    res = client.post(
        "/api/chat",
        json={
            "message": "What is the status of the refinery units?",
            "history": [
                {"role": "user", "content": "Hello workbench"},
                {"role": "assistant", "content": "DRISHTI Sovereign Copilot ready."},
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True


def test_cors_hotspot_and_lan_support():
    """Verify CORS middleware permits private RFC-1918 subnets (hotspot, LAN) and rejects external WAN origins."""
    # 1. Hotspot IP (192.168.x.x) should be permitted
    res_hotspot = client.get("/api/health", headers={"Origin": "http://192.168.8.244:8000"})
    assert res_hotspot.status_code == 200
    assert res_hotspot.headers.get("access-control-allow-origin") == "http://192.168.8.244:8000"
    assert res_hotspot.headers.get("access-control-allow-credentials") == "true"

    # 2. Private LAN IP (10.x.x.x) should be permitted
    res_lan = client.get("/api/health", headers={"Origin": "http://10.0.0.5:8000"})
    assert res_lan.status_code == 200
    assert res_lan.headers.get("access-control-allow-origin") == "http://10.0.0.5:8000"

    # 3. External public internet origin must NOT be permitted
    res_evil = client.get("/api/health", headers={"Origin": "https://external-cloud.com"})
    assert res_evil.status_code == 200
    assert res_evil.headers.get("access-control-allow-origin") != "https://external-cloud.com"



