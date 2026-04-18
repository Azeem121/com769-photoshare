"""
Smoke test for the health function — verifies the response shape without
requiring any Azure connection.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Minimal stub so azure.functions can be imported without a real host
try:
    import azure.functions as func
except ImportError:
    pytest.skip("azure-functions not installed", allow_module_level=True)

import importlib, types

# Load the health function module directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "health",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "health", "__init__.py"),
)
health_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health_module)


class _FakeRequest:
    headers = {}
    params = {}
    route_params = {}

    def get_body(self):
        return b""

    def get_json(self):
        raise ValueError


def test_health_returns_200():
    response = health_module.main(_FakeRequest())
    assert response.status_code == 200


def test_health_body_has_status():
    response = health_module.main(_FakeRequest())
    body = json.loads(response.get_body().decode())
    assert body["status"] == "healthy"
    assert "timestamp" in body
    assert "version" in body
