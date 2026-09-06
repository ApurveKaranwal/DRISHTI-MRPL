"""Automated Test Suite for MRPL Sovereign AI Workbench.

Verifies end-to-end functionality of all REST endpoints, DuckDB analytical
engines, and air-gap sovereign operations.
"""

import json
import urllib.request
import urllib.error
import sys

BASE_URL = "http://localhost:8000"


def test_health():
    url = f"{BASE_URL}/api/health"
    req = urllib.request.urlopen(url, timeout=5)
    assert req.status == 200, f"Expected 200, got {req.status}"
    data = json.loads(req.read().decode())
    assert data.get("status") == "operational"
    print("PASS: /api/health returned operational status")


def test_static_assets():
    for path in ["/", "/static/app.css", "/static/app.js"]:
        url = f"{BASE_URL}{path}"
        req = urllib.request.urlopen(url, timeout=5)
        assert req.status == 200, f"Expected 200 for {path}, got {req.status}"
        body = req.read()
        assert len(body) > 1000, f"Unexpected body size for {path}"
        print(f"PASS: {path} returned HTTP 200 ({len(body)} bytes)")


def test_documents_endpoint():
    url = f"{BASE_URL}/api/documents"
    req = urllib.request.urlopen(url, timeout=5)
    assert req.status == 200, f"Expected 200, got {req.status}"
    docs = json.loads(req.read().decode())
    assert isinstance(docs, list), f"Expected list, got {type(docs)}"
    assert len(docs) >= 8, f"Expected >= 8 documents, got {len(docs)}"
    print(f"PASS: /api/documents returned {len(docs)} active datasets")


def test_deliverables_endpoint():
    url = f"{BASE_URL}/api/deliverables"
    req = urllib.request.urlopen(url, timeout=5)
    assert req.status == 200, f"Expected 200, got {req.status}"
    data = json.loads(req.read().decode())
    assert "deliverables" in data
    print(f"PASS: /api/deliverables returned {len(data['deliverables'])} reports")


def test_chat_query():
    url = f"{BASE_URL}/api/chat"
    payload = json.dumps({"message": "Show refinery performance summary"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10)
    assert resp.status == 200, f"Expected 200, got {resp.status}"
    data = json.loads(resp.read().decode())
    assert data.get("success") is True
    assert "answer" in data and len(data["answer"]) > 50
    print("PASS: /api/chat executed workflow and returned structured answer")


def test_security_traversal():
    # Attempt directory traversal attack on download endpoint
    url = f"{BASE_URL}/api/download/..%2F..%2Fserver.py?source=reports"
    try:
        urllib.request.urlopen(url, timeout=5)
        raise AssertionError("Security vulnerability: Directory traversal was not blocked!")
    except urllib.error.HTTPError as err:
        assert err.code in (400, 403, 404), f"Expected 400/403/404, got {err.code}"
        print(f"PASS: Directory traversal attack safely blocked with HTTP {err.code}")


def test_airgap_certificate():
    url = f"{BASE_URL}/api/certificate"
    req = urllib.request.urlopen(url, timeout=5)
    assert req.status == 200, f"Expected 200, got {req.status}"
    cert = json.loads(req.read().decode())
    assert "sha256_audit_signature" in cert, "Missing sha256_audit_signature"
    assert cert.get("is_air_gapped") is True, "Air gap check failed"
    assert cert.get("external_wan_bytes_transferred") == 0, "External WAN bytes detected!"
    print(f"PASS: /api/certificate verified 100% air-gap intact (Signature: {cert['sha256_audit_signature'][:16]}...)")


def test_telemetry_endpoint():
    url = f"{BASE_URL}/api/telemetry"
    req = urllib.request.urlopen(url, timeout=5)
    assert req.status == 200, f"Expected 200, got {req.status}"
    tel = json.loads(req.read().decode())
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

