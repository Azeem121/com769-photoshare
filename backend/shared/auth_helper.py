"""
Token-based authentication helper.

Tokens are stored in Cosmos DB "tokens" container.
Users are stored in "users" container.
Role is derived from username: suffix @creator -> creator, else consumer.
"""

import hashlib
import json
import logging
import secrets
from typing import Optional

import azure.functions as func

from shared import cosmos_client

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    return hash_password(password) == stored_hash


def generate_token() -> str:
    return secrets.token_hex(32)


def make_response(body: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body),
        status_code=status_code,
        mimetype="application/json",
        headers=CORS_HEADERS,
    )


def options_response() -> func.HttpResponse:
    return func.HttpResponse(status_code=200, headers=CORS_HEADERS)


def json_401(message: str = "Authentication required") -> func.HttpResponse:
    return make_response({"error": message}, 401)


def json_403(message: str = "Forbidden") -> func.HttpResponse:
    return make_response({"error": message}, 403)


def parse_auth_header(req: func.HttpRequest) -> Optional[str]:
    auth = req.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def get_current_user(req: func.HttpRequest) -> Optional[dict]:
    token = parse_auth_header(req)
    if not token:
        return None
    try:
        # Cross-partition query works regardless of the container's partition key setting
        results = cosmos_client.query_items(
            "tokens",
            "SELECT * FROM c WHERE c.id = @token",
            [{"name": "@token", "value": token}],
        )
        return results[0] if results else None
    except Exception as exc:
        logging.warning("Token lookup failed: %s", exc)
        return None


def require_role(req: func.HttpRequest, role: str) -> dict:
    user = get_current_user(req)
    if not user:
        raise PermissionError("Authentication required")
    if user.get("role") != role:
        raise PermissionError(f'Role "{role}" required')
    return user


def get_user_id(user: dict) -> str:
    return user.get("userId", "")


def get_username(user: dict) -> str:
    return user.get("username", "")
