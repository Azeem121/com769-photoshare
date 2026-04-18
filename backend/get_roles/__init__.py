"""
Azure Static Web Apps custom roles function.

SWA calls POST /api/GetRoles after a user authenticates, passing the user's
identity in the request body.  This function looks up the user in Cosmos DB to
find their assigned role (creator / consumer) and returns it.

If the user does not exist they are auto-created with the "consumer" role, which
means every new sign-up becomes a consumer by default.
Creator accounts must be seeded directly in the Cosmos DB "users" container by
an administrator — there is no public creator registration endpoint.

SWA then embeds the returned roles in the x-ms-client-principal header on every
subsequent API request for the lifetime of the session.
"""

import json
import logging
from datetime import datetime, timezone

import azure.functions as func

from shared import cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("GetRoles called")

    try:
        body = req.get_json()
    except ValueError:
        body = {}

    user_id = body.get("userId", "")
    user_details = body.get("userDetails", "")
    identity_provider = body.get("identityProvider", "")

    if not user_id:
        return func.HttpResponse(
            json.dumps({"roles": []}),
            status_code=200,
            mimetype="application/json",
        )

    # Look up existing user record
    user = cosmos_client.get_item("users", user_id, user_id)

    if user is None:
        # First login — create consumer account
        user = {
            "id": user_id,
            "userId": user_id,
            "email": user_details,
            "displayName": user_details.split("@")[0] if "@" in user_details else user_details,
            "role": "consumer",
            "identityProvider": identity_provider,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        cosmos_client.upsert_item("users", user)
        logging.info("Created new consumer user: %s", user_id)

    role = user.get("role", "consumer")
    return func.HttpResponse(
        json.dumps({"roles": ["authenticated", role]}),
        status_code=200,
        mimetype="application/json",
    )
