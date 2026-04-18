"""
GET /api/auth/me  — returns current user from Bearer token

Returns 401 if no valid token is provided.
"""

import logging

import azure.functions as func

from shared import auth_helper


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    logging.info("auth_me triggered")

    user = auth_helper.get_current_user(req)
    if not user:
        return auth_helper.json_401("No valid session token")

    return auth_helper.make_response({
        "userId": auth_helper.get_user_id(user),
        "username": auth_helper.get_username(user),
        "role": user.get("role", "consumer"),
    })
