"""
GET /api/photos/my  — creator only

Returns all photos uploaded by the currently authenticated creator,
ordered newest first.
"""

import logging

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    logging.info("photos_my triggered")

    try:
        user = auth_helper.require_role(req, "creator")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(user)

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
        return auth_helper.make_response({"error": "Failed to retrieve your photos"}, 500)

    return auth_helper.make_response({"photos": photos})
