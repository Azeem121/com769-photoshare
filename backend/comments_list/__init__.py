"""
GET /api/photos/{id}/comments  — public

Returns all comments for a photo, ordered oldest-first.
"""

import logging

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    photo_id = req.route_params.get("id", "")
    logging.info("comments_list triggered for photo_id=%s", photo_id)

    query = """
        SELECT c.id, c.authorName, c.text, c.createdAt
        FROM c
        WHERE c.photoId = @photoId
        ORDER BY c.createdAt ASC
    """
    parameters = [{"name": "@photoId", "value": photo_id}]

    try:
        comments = cosmos_client.query_items("comments", query, parameters)
    except Exception as exc:
        logging.error("Cosmos DB query failed: %s", exc)
        return auth_helper.make_response({"error": "Failed to retrieve comments"}, 500)

    return auth_helper.make_response({"comments": comments, "total": len(comments)})
