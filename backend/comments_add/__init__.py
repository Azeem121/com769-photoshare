"""
POST /api/photos/{id}/comment  — consumer only

Body (JSON):
  text : string (required, max 1 000 chars)
"""

import logging
import uuid
from datetime import datetime, timezone

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    photo_id = req.route_params.get("id", "")
    logging.info("comments_add triggered for photo_id=%s", photo_id)

    try:
        user = auth_helper.require_role(req, "consumer")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(user)
    display_name = auth_helper.get_username(user)

    try:
        body = req.get_json()
    except ValueError:
        return auth_helper.make_response({"error": "Request body must be JSON"}, 400)

    text = (body.get("text") or "").strip()
    if not text:
        return auth_helper.make_response({"error": "text is required"}, 400)
    if len(text) > 1000:
        return auth_helper.make_response({"error": "Comment must be 1 000 characters or fewer"}, 400)

    photo_query = "SELECT VALUE COUNT(1) FROM c WHERE c.id = @id"
    photo_params = [{"name": "@id", "value": photo_id}]
    try:
        count = cosmos_client.query_items("photos", photo_query, photo_params)
        if not count or count[0] == 0:
            return auth_helper.make_response({"error": "Photo not found"}, 404)
    except Exception as exc:
        logging.error("Photo existence check failed: %s", exc)

    now = datetime.now(timezone.utc).isoformat()
    comment = {
        "id": str(uuid.uuid4()),
        "photoId": photo_id,
        "authorId": user_id,
        "authorName": display_name,
        "text": text,
        "createdAt": now,
    }

    try:
        cosmos_client.create_item("comments", comment)
    except Exception as exc:
        logging.error("Failed to save comment: %s", exc)
        return auth_helper.make_response({"error": "Failed to save comment"}, 500)

    return auth_helper.make_response(comment, 201)
