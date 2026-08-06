"""API smoke tests: health and metrics surfaces."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness() -> None:
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_metrics_exposed() -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
    assert "conductor_cost_usd_total" in resp.text


def test_not_found_uses_error_envelope() -> None:
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert "error" in resp.json()
    assert resp.json()["error"]["code"] == "not_found"