"""
GET /api/photos/my  — creator only

Returns all photos uploaded by the currently authenticated creator,
ordered newest first.
"""

import json
import logging

import azure.functions as func
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("photos_my triggered")

    try:
        principal = auth_helper.require_role(req, "creator")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(principal)

    query = """
        SELECT c.id, c.title, c.caption, c.location, c.people,
               c.imageUrl, c.avgRating, c.ratingCount,
               c.aiTags, c.aiDescription, c.createdAt
        FROM c
        WHERE c.uploadedBy = @userId
        ORDER BY c.createdAt DESC
    """
    parameters = [{"name": "@userId", "value": user_id}]

    try:
        photos = cosmos_client.query_items("photos", query, parameters)
    except Exception as exc:
        logging.error("Cosmos DB query failed: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Failed to retrieve your photos"}),
            status_code=500, mimetype="application/json",
        )

    return func.HttpResponse(
        json.dumps({"photos": photos}),
        status_code=200,
        mimetype="application/json",
    )
