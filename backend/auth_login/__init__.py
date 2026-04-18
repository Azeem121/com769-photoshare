"""
POST /api/auth/login  — register or login

Body (JSON):
  username : string (required)
  password : string (required)

If the user does not exist, creates an account automatically.
Role is derived from username: suffix @creator -> creator, else consumer.
Returns a Bearer token stored in Cosmos DB.
"""

import logging
from datetime import datetime, timezone

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    logging.info("auth_login triggered")

    try:
        body = req.get_json()
    except ValueError:
        return auth_helper.make_response({"error": "Request body must be JSON"}, 400)

    username = (body.get("username") or "").strip()
    password = (body.get("password") or "").strip()

    if not username or not password:
        return auth_helper.make_response({"error": "username and password are required"}, 400)

    if len(password) < 4:
        return auth_helper.make_response({"error": "password must be at least 4 characters"}, 400)

    role = "creator" if username.endswith("@creator") else "consumer"
    now = datetime.now(timezone.utc).isoformat()

    # Look up existing user
    try:
        existing = cosmos_client.get_item("auth_users", username, username)
    except Exception as exc:
        logging.exception("Failed to read auth_users container")
        return auth_helper.make_response({
            "error": "Database read error",
            "detail": str(exc),
            "type": type(exc).__name__,
        }, 500)

    if existing:
        if not auth_helper.verify_password(password, existing.get("passwordHash", "")):
            return auth_helper.make_response({"error": "Invalid username or password"}, 401)
        role = existing.get("role", role)
    else:
        user_doc = {
            "id": username,
            "userId": username,
            "username": username,
            "passwordHash": auth_helper.hash_password(password),
            "role": role,
            "createdAt": now,
        }
        try:
            cosmos_client.create_item("auth_users", user_doc)
        except Exception as exc:
            logging.exception("Failed to create user in auth_users")
            return auth_helper.make_response({
                "error": "Failed to create account",
                "detail": str(exc),
                "type": type(exc).__name__,
            }, 500)

    token = auth_helper.generate_token()
    token_doc = {
        "id": token,
        "userId": username,
        "username": username,
        "role": role,
        "createdAt": now,
    }

    try:
        cosmos_client.create_item("tokens", token_doc)
    except Exception as exc:
        logging.exception("Failed to create token in tokens container")
        return auth_helper.make_response({
            "error": "Failed to generate session",
            "detail": str(exc),
            "type": type(exc).__name__,
        }, 500)

    logging.info("auth_login success for user=%s role=%s", username, role)
    return auth_helper.make_response({
        "token": token,
        "userId": username,
        "username": username,
        "role": role,
    }, 200)
