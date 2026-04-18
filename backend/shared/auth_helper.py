"""
Azure Static Web Apps authentication helper.

SWA injects x-ms-client-principal into every request reaching /api/*.
The header is a base64-encoded JSON blob containing userId, userDetails
(the email / username), userRoles, and identityProvider.

Roles are populated by the GetRoles function (rolesSource in
staticwebapp.config.json).  Every authenticated user has "authenticated";
creators have "creator"; consumers have "consumer".
"""

import base64
import json
import logging
from typing import Optional

import azure.functions as func


def parse_principal(req: func.HttpRequest) -> Optional[dict]:
    header = req.headers.get("x-ms-client-principal")
    if not header:
        return None
    try:
        # Azure pads to multiples of 4 itself, but add == to be safe
        decoded = base64.b64decode(header + "==").decode("utf-8")
        return json.loads(decoded)
    except Exception as exc:
        logging.warning("Failed to parse x-ms-client-principal: %s", exc)
        return None


def get_user_id(principal: dict) -> str:
    return principal.get("userId", "")


def get_user_email(principal: dict) -> str:
    return principal.get("userDetails", "")


def get_roles(principal: dict) -> list:
    return principal.get("userRoles", [])


def is_authenticated(principal: Optional[dict]) -> bool:
    return bool(principal) and "authenticated" in get_roles(principal)


def has_role(principal: Optional[dict], role: str) -> bool:
    return bool(principal) and role in get_roles(principal)


def require_auth(req: func.HttpRequest) -> dict:
    principal = parse_principal(req)
    if not is_authenticated(principal):
        raise PermissionError("Authentication required")
    return principal


def require_role(req: func.HttpRequest, role: str) -> dict:
    principal = require_auth(req)
    if not has_role(principal, role):
        raise PermissionError(f'Role "{role}" required')
    return principal


def json_401(message: str = "Authentication required") -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": message}),
        status_code=401,
        mimetype="application/json",
    )


def json_403(message: str = "Forbidden") -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"error": message}),
        status_code=403,
        mimetype="application/json",
    )
