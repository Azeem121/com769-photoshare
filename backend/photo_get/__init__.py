"""
GET /api/photos/{id}  — public

Returns the full photo document along with its comments and average rating.
The caller's own rating is included when they are authenticated (so the UI
can pre-fill the star selector).
"""

import json
import logging

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    photo_id = req.route_params.get("id", "")
    logging.info("photo_get triggered for id=%s", photo_id)

    # Fetch photo — partition key is uploadedBy (cross-partition read)
    query = "SELECT * FROM c WHERE c.id = @id"
    params = [{"name": "@id", "value": photo_id}]

    try:
        results = cosmos_client.query_items("photos", query, params)
    except Exception as exc:
        logging.error("Cosmos DB query failed: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Database error"}),
            status_code=500, mimetype="application/json",
        )

    if not results:
        return func.HttpResponse(
            json.dumps({"error": "Photo not found"}),
            status_code=404, mimetype="application/json",
        )

    photo = results[0]

    # Fetch comments for this photo
    comment_query = """
        SELECT c.id, c.authorEmail, c.authorName, c.text, c.createdAt
        FROM c
        WHERE c.photoId = @photoId
        ORDER BY c.createdAt ASC
    """
    comment_params = [{"name": "@photoId", "value": photo_id}]

    try:
        comments = cosmos_client.query_items("comments", comment_query, comment_params)
    except Exception as exc:
        logging.warning("Failed to load comments: %s", exc)
        comments = []

    # Check if authenticated user has already rated this photo
    own_rating = None
    principal = auth_helper.parse_principal(req)
    if auth_helper.is_authenticated(principal):
        user_id = auth_helper.get_user_id(principal)
        rating_id = f"{user_id}_{photo_id}"
        try:
            rating_doc = cosmos_client.get_item("ratings", rating_id, photo_id)
            if rating_doc:
                own_rating = rating_doc.get("rating")
        except Exception:
            pass

    photo["comments"] = comments
    photo["ownRating"] = own_rating

    return func.HttpResponse(
        json.dumps(photo),
        status_code=200,
        mimetype="application/json",
    )
