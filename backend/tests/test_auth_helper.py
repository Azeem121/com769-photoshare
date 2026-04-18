"""
Unit tests for shared/auth_helper.py

These tests run without any Azure connection — they mock Cosmos DB lookups
and only exercise local token/role logic.
"""

import sys
import os
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import auth_helper


class _FakeRequest:
    def __init__(self, auth_header=None, method="GET"):
        self.headers = {}
        self.method = method
        if auth_header:
            self.headers["Authorization"] = auth_header


# ── hash_password / verify_password ──────────────────────────────────────────

def test_hash_password_is_deterministic():
    h = auth_helper.hash_password("secret")
    assert auth_helper.hash_password("secret") == h


def test_verify_password_correct():
    h = auth_helper.hash_password("mypassword")
    assert auth_helper.verify_password("mypassword", h) is True


def test_verify_password_wrong():
    h = auth_helper.hash_password("mypassword")
    assert auth_helper.verify_password("wrong", h) is False


# ── generate_token ────────────────────────────────────────────────────────────

def test_generate_token_length():
    token = auth_helper.generate_token()
    assert len(token) == 64  # secrets.token_hex(32) -> 64 hex chars


def test_generate_token_unique():
    assert auth_helper.generate_token() != auth_helper.generate_token()


# ── parse_auth_header ─────────────────────────────────────────────────────────

def test_parse_auth_header_valid():
    req = _FakeRequest(auth_header="Bearer mytoken123")
    assert auth_helper.parse_auth_header(req) == "mytoken123"


def test_parse_auth_header_missing():
    req = _FakeRequest()
    assert auth_helper.parse_auth_header(req) is None


def test_parse_auth_header_wrong_scheme():
    req = _FakeRequest(auth_header="Basic abc123")
    assert auth_helper.parse_auth_header(req) is None


# ── get_user_id / get_username ────────────────────────────────────────────────

def test_get_user_id():
    user = {"userId": "alice@creator", "username": "alice@creator", "role": "creator"}
    assert auth_helper.get_user_id(user) == "alice@creator"


def test_get_username():
    user = {"userId": "bob", "username": "bob", "role": "consumer"}
    assert auth_helper.get_username(user) == "bob"


# ── get_current_user ──────────────────────────────────────────────────────────

def test_get_current_user_no_token():
    req = _FakeRequest()
    result = auth_helper.get_current_user(req)
    assert result is None


def test_get_current_user_valid_token():
    fake_user = {"id": "tok", "userId": "alice", "username": "alice", "role": "consumer"}
    req = _FakeRequest(auth_header="Bearer tok")
    with patch("shared.auth_helper.cosmos_client") as mock_cosmos:
        mock_cosmos.get_item.return_value = fake_user
        result = auth_helper.get_current_user(req)
    assert result == fake_user


def test_get_current_user_token_not_found():
    req = _FakeRequest(auth_header="Bearer badtoken")
    with patch("shared.auth_helper.cosmos_client") as mock_cosmos:
        mock_cosmos.get_item.return_value = None
        result = auth_helper.get_current_user(req)
    assert result is None


# ── require_role ──────────────────────────────────────────────────────────────

def test_require_role_raises_when_unauthenticated():
    req = _FakeRequest()
    with pytest.raises(PermissionError):
        auth_helper.require_role(req, "creator")


def test_require_role_raises_wrong_role():
    fake_user = {"id": "tok", "userId": "bob", "username": "bob", "role": "consumer"}
    req = _FakeRequest(auth_header="Bearer tok")
    with patch("shared.auth_helper.cosmos_client") as mock_cosmos:
        mock_cosmos.get_item.return_value = fake_user
        with pytest.raises(PermissionError):
            auth_helper.require_role(req, "creator")


def test_require_role_passes_correct_role():
    fake_user = {"id": "tok", "userId": "alice@creator", "username": "alice@creator", "role": "creator"}
    req = _FakeRequest(auth_header="Bearer tok")
    with patch("shared.auth_helper.cosmos_client") as mock_cosmos:
        mock_cosmos.get_item.return_value = fake_user
        user = auth_helper.require_role(req, "creator")
    assert user is not None
    assert user["role"] == "creator"


# ── json_401 / json_403 ───────────────────────────────────────────────────────

def test_json_401_status():
    resp = auth_helper.json_401()
    assert resp.status_code == 401


def test_json_403_status():
    resp = auth_helper.json_403()
    assert resp.status_code == 403


def test_cors_headers_present():
    resp = auth_helper.make_response({"ok": True}, 200)
    assert "Access-Control-Allow-Origin" in resp.headers
