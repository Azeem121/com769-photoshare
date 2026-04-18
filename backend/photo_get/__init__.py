"""
GET /api/photos/{id}  — public

Returns the full photo document along with its comments and average rating.
The caller's own rating is included when they are authenticated (so the UI
can pre-fill the star selector).
"""

import logging

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    photo_id = req.route_params.get("id", "")
    logging.info("photo_get triggered for id=%s", photo_id)

    query = "SELECT * FROM c WHERE c.id = @id"
    params = [{"name": "@id", "value": photo_id}]

    try:
        results = cosmos_client.query_items("photos", query, params)
    except Exception as exc:
        logging.error("Cosmos DB query failed: %s", exc)
        return auth_helper.make_response({"error": "Database error"}, 500)

    if not results:
        return auth_helper.make_response({"error": "Photo not found"}, 404)

    photo = results[0]

    comment_query = """
        SELECT c.id, c.authorName, c.text, c.createdAt
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

    own_rating = None
    user = auth_helper.get_current_user(req)
    if user:
        user_id = auth_helper.get_user_id(user)
        rating_id = f"{user_id}_{photo_id}"
        try:
            rating_doc = cosmos_client.get_item("ratings", rating_id, rating_id)
            if rating_doc:
                own_rating = rating_doc.get("rating")
        except Exception:
            pass

    photo["comments"] = comments
    photo["ownRating"] = own_rating

    return auth_helper.make_response(photo)
