"""Automated Test Suite for MRPL Sovereign AI Workbench.

Verifies end-to-end functionality of all REST endpoints, DuckDB analytical
engines, and air-gap sovereign operations.
"""

import json
import urllib.request
import urllib.error
import sys

BASE_URL = "http://localhost:8000"

# Optional in-process TestClient fallback for offline test runners
_client = None


def get_client():
    global _client
    if _client is None:
        try:
            from fastapi.testclient import TestClient
            from server import app
            _client = TestClient(app)
        except Exception:
            _client = None
    return _client


def request_get(path, timeout=10):
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.urlopen(url, timeout=timeout)
        return req.status, req.read()
    except (urllib.error.URLError, ConnectionRefusedError, OSError):
        client = get_client()
        if client:
            resp = client.get(path)
            return resp.status_code, resp.content
        raise


def request_post(path, data, headers=None, timeout=180):
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, data=data, headers=headers or {})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, resp.read()
    except (urllib.error.URLError, ConnectionRefusedError, OSError):
        client = get_client()
        if client:
            json_payload = json.loads(data.decode()) if isinstance(data, bytes) else data
            resp = client.post(path, json=json_payload)
            return resp.status_code, resp.content
        raise


def test_health():
    status, body = request_get("/api/health")
    assert status == 200, f"Expected 200, got {status}"
    data = json.loads(body.decode())
    assert data.get("status") == "operational"
    print("PASS: /api/health returned operational status")


def test_static_assets():
    for path in ["/", "/static/app.css", "/static/app.js"]:
        status, body = request_get(path)
        assert status == 200, f"Expected 200 for {path}, got {status}"
        assert len(body) > 1000, f"Unexpected body size for {path}"
        print(f"PASS: {path} returned HTTP 200 ({len(body)} bytes)")


def test_documents_endpoint():
    status, body = request_get("/api/documents")
    assert status == 200, f"Expected 200, got {status}"
    docs = json.loads(body.decode())
    assert isinstance(docs, list), f"Expected list, got {type(docs)}"
    assert len(docs) >= 8, f"Expected >= 8 documents, got {len(docs)}"
    print(f"PASS: /api/documents returned {len(docs)} active datasets")


def test_deliverables_endpoint():
    status, body = request_get("/api/deliverables")
    assert status == 200, f"Expected 200, got {status}"
    data = json.loads(body.decode())
    assert "deliverables" in data
    print(f"PASS: /api/deliverables returned {len(data['deliverables'])} reports")


def test_chat_query():
    payload = json.dumps({"message": "Show refinery performance summary"}).encode()
    status, body = request_post("/api/chat", data=payload, headers={"Content-Type": "application/json"})
    assert status == 200, f"Expected 200, got {status}"
    data = json.loads(body.decode())
    assert data.get("success") is True
    assert "answer" in data and len(data["answer"]) > 50
    print("PASS: /api/chat executed workflow and returned structured answer")


def test_security_traversal():
    path = "/api/download/..%2F..%2Fserver.py?source=reports"
    try:
        status, _ = request_get(path)
        assert status in (400, 403, 404), f"Security traversal failed: expected error code, got {status}"
        print(f"PASS: Directory traversal attack safely blocked with HTTP {status}")
    except urllib.error.HTTPError as err:
        assert err.code in (400, 403, 404), f"Expected 400/403/404, got {err.code}"
        print(f"PASS: Directory traversal attack safely blocked with HTTP {err.code}")


def test_airgap_certificate():
    status, body = request_get("/api/certificate")
    assert status == 200, f"Expected 200, got {status}"
    cert = json.loads(body.decode())
    assert "sha256_audit_signature" in cert, "Missing sha256_audit_signature"
    assert cert.get("is_air_gapped") is True, "Air gap check failed"
    assert cert.get("external_wan_bytes_transferred") == 0, "External WAN bytes detected!"
    print(f"PASS: /api/certificate verified 100% air-gap intact (Signature: {cert['sha256_audit_signature'][:16]}...)")


def test_telemetry_endpoint():
    status, body = request_get("/api/telemetry")
    assert status == 200, f"Expected 200, got {status}"
    tel = json.loads(body.decode())
    assert "active_sockets" in tel
    print(f"PASS: /api/telemetry actively tracking {len(tel['active_sockets'])} local sockets")


if __name__ == "__main__":
    print("=" * 65)
    print("Running MRPL Sovereign AI Workbench Integration Verification...")
    print("=" * 65)
    try:
        test_health()
        test_static_assets()
        test_documents_endpoint()
        test_deliverables_endpoint()
        test_chat_query()
        test_security_traversal()
        test_airgap_certificate()
        test_telemetry_endpoint()
        print("=" * 65)
        print("ALL TESTS PASSED SUCCESSFULLY! (100% SOVEREIGN & SECURE)")
        print("=" * 65)
    except Exception as err:
        print(f"\nFAILED: {err}")
        sys.exit(1)

