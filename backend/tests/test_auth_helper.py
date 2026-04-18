"""
Unit tests for shared/auth_helper.py

These tests run without any Azure connection — they only exercise the local
principal-parsing and role-checking logic.
"""

import base64
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import auth_helper


def _make_principal(user_id="u1", user_details="test@example.com", roles=None):
    if roles is None:
        roles = ["authenticated", "consumer"]
    payload = {
        "userId": user_id,
        "userDetails": user_details,
        "userRoles": roles,
        "identityProvider": "github",
    }
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    return encoded


class _FakeRequest:
    def __init__(self, header_value=None):
        self.headers = {}
        if header_value:
            self.headers["x-ms-client-principal"] = header_value


# ── parse_principal ───────────────────────────────────────────────────────────

def test_parse_principal_valid():
    req = _FakeRequest(_make_principal())
    p = auth_helper.parse_principal(req)
    assert p is not None
    assert p["userId"] == "u1"
    assert p["userDetails"] == "test@example.com"


def test_parse_principal_missing_header():
    req = _FakeRequest()
    assert auth_helper.parse_principal(req) is None


def test_parse_principal_malformed_header():
    req = _FakeRequest("not-valid-base64!!!")
    assert auth_helper.parse_principal(req) is None


# ── role helpers ──────────────────────────────────────────────────────────────

def test_get_user_id():
    p = {"userId": "abc", "userRoles": ["authenticated"]}
    assert auth_helper.get_user_id(p) == "abc"


def test_get_user_email():
    p = {"userDetails": "alice@example.com", "userRoles": []}
    assert auth_helper.get_user_email(p) == "alice@example.com"


def test_is_authenticated_true():
    req = _FakeRequest(_make_principal(roles=["authenticated", "consumer"]))
    p = auth_helper.parse_principal(req)
    assert auth_helper.is_authenticated(p) is True


def test_is_authenticated_false_no_role():
    req = _FakeRequest(_make_principal(roles=["anonymous"]))
    p = auth_helper.parse_principal(req)
    assert auth_helper.is_authenticated(p) is False


def test_is_authenticated_none():
    assert auth_helper.is_authenticated(None) is False


def test_has_role_creator():
    req = _FakeRequest(_make_principal(roles=["authenticated", "creator"]))
    p = auth_helper.parse_principal(req)
    assert auth_helper.has_role(p, "creator") is True
    assert auth_helper.has_role(p, "consumer") is False


def test_has_role_none_principal():
    assert auth_helper.has_role(None, "creator") is False


# ── require_auth / require_role ───────────────────────────────────────────────

def test_require_auth_success():
    req = _FakeRequest(_make_principal(roles=["authenticated", "consumer"]))
    p = auth_helper.require_auth(req)
    assert p["userId"] == "u1"


def test_require_auth_raises_when_unauthenticated():
    req = _FakeRequest()
    with pytest.raises(PermissionError):
        auth_helper.require_auth(req)


def test_require_role_raises_wrong_role():
    req = _FakeRequest(_make_principal(roles=["authenticated", "consumer"]))
    with pytest.raises(PermissionError):
        auth_helper.require_role(req, "creator")


def test_require_role_passes_correct_role():
    req = _FakeRequest(_make_principal(roles=["authenticated", "creator"]))
    p = auth_helper.require_role(req, "creator")
    assert p is not None
