"""
API Tests for Health, System Diagnostics, and Security Middleware.
"""
import pytest


def test_root_health(client):
    """Test public health endpoint returns 200 and valid json."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Hospital Lead" in data["app"]


def test_core_health_deep_check(client):
    """Test deep system healthcheck verifying DB, task queue, and scheduler."""
    response = client.get("/api/v1/core/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "services" in data
    assert "database" in data["services"]
    assert "task_queue" in data["services"]
    assert "scheduler" in data["services"]
    assert data["services"]["database"]["healthy"] is True


def test_core_system_info(client):
    """Test non-sensitive system info endpoint."""
    response = client.get("/api/v1/core/info")
    assert response.status_code == 200
    data = response.json()
    assert len(data["modules_active"]) == 11
    assert "Leads" in data["modules_active"]
    assert "Calls" in data["modules_active"]


def test_security_headers_present(client):
    """Verify security headers are applied to HTTP responses."""
    response = client.get("/api/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time-Ms" in response.headers
