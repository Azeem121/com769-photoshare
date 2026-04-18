"""
POST /api/photos/{id}/comment  — consumer only

Body (JSON):
  text : string (required, max 1 000 chars)
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    photo_id = req.route_params.get("id", "")
    logging.info("comments_add triggered for photo_id=%s", photo_id)

    try:
        principal = auth_helper.require_role(req, "consumer")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(principal)
    user_email = auth_helper.get_user_email(principal)
    display_name = user_email.split("@")[0] if "@" in user_email else user_email

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Request body must be JSON"}),
            status_code=400, mimetype="application/json",
        )

    text = (body.get("text") or "").strip()
    if not text:
        return func.HttpResponse(
            json.dumps({"error": "text is required"}),
            status_code=400, mimetype="application/json",
        )
    if len(text) > 1000:
        return func.HttpResponse(
            json.dumps({"error": "Comment must be 1 000 characters or fewer"}),
            status_code=400, mimetype="application/json",
        )

    # Verify the photo exists
    photo_query = "SELECT VALUE COUNT(1) FROM c WHERE c.id = @id"
    photo_params = [{"name": "@id", "value": photo_id}]
    try:
        count = cosmos_client.query_items("photos", photo_query, photo_params)
        if not count or count[0] == 0:
            return func.HttpResponse(
                json.dumps({"error": "Photo not found"}),
                status_code=404, mimetype="application/json",
            )
    except Exception as exc:
        logging.error("Photo existence check failed: %s", exc)

    now = datetime.now(timezone.utc).isoformat()
    comment = {
        "id": str(uuid.uuid4()),
        "photoId": photo_id,
        "authorId": user_id,
        "authorEmail": user_email,
        "authorName": display_name,
        "text": text,
        "createdAt": now,
    }

    try:
        cosmos_client.create_item("comments", comment)
    except Exception as exc:
        logging.error("Failed to save comment: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Failed to save comment"}),
            status_code=500, mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps(comment),
        status_code=201,
        mimetype="application/json",
    )
