"""
GET  /api/photos/{id}  — public: returns photo + comments + own rating
DELETE /api/photos/{id} — creator only, must own the photo

Combined into one function to avoid route conflict in Azure Functions host.
"""

import logging

import azure.functions as func

from shared import auth_helper, blob_client, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    photo_id = req.route_params.get("id", "")

    if req.method == "DELETE":
        return _handle_delete(req, photo_id)
    return _handle_get(req, photo_id)


def _handle_get(req: func.HttpRequest, photo_id: str) -> func.HttpResponse:
    logging.info("photo_get GET id=%s", photo_id)

    query = "SELECT * FROM c WHERE c.id = @id"
    params = [{"name": "@id", "value": photo_id}]

    try:
        results = cosmos_client.query_items("photos", query, params)
    except Exception as exc:
        logging.error("Cosmos query failed: %s", exc)
        return auth_helper.make_response({"error": "Database error"}, 500)

    if not results:
        return auth_helper.make_response({"error": "Photo not found"}, 404)

    photo = results[0]

    # Load comments (ORDER BY requires composite index; fall back to unsorted if it fails)
    try:
        comments = cosmos_client.query_items(
            "comments",
            "SELECT c.id, c.authorName, c.text, c.createdAt FROM c WHERE c.photoId = @pid",
            [{"name": "@pid", "value": photo_id}],
        )
    except Exception as exc:
        logging.warning("Comments query failed: %s", exc)
        comments = []

    # Own rating for authenticated user
    own_rating = None
    user = auth_helper.get_current_user(req)
    if user:
        user_id = auth_helper.get_user_id(user)
        try:
            rating_doc = cosmos_client.get_item("ratings", f"{user_id}_{photo_id}", f"{user_id}_{photo_id}")
            if rating_doc:
                own_rating = rating_doc.get("rating")
        except Exception:
            pass

    photo["comments"] = comments
    photo["ownRating"] = own_rating
    return auth_helper.make_response(photo)


def _handle_delete(req: func.HttpRequest, photo_id: str) -> func.HttpResponse:
    logging.info("photo_delete DELETE id=%s", photo_id)

    try:
        user = auth_helper.require_role(req, "creator")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(user)

    try:
        results = cosmos_client.query_items(
            "photos",
            "SELECT * FROM c WHERE c.id = @id",
            [{"name": "@id", "value": photo_id}],
        )
    except Exception as exc:
        logging.error("Cosmos query failed: %s", exc)
        return auth_helper.make_response({"error": "Database error"}, 500)

    if not results:
        return auth_helper.make_response({"error": "Photo not found"}, 404)

    photo = results[0]

    if photo.get("uploadedBy") != user_id:
        return auth_helper.make_response({"error": "You can only delete your own photos"}, 403)

    blob_name = photo.get("blobName", "")
    if blob_name:
        try:
            blob_client.delete_photo(blob_name)
        except Exception as exc:
            logging.warning("Blob delete failed (continuing): %s", exc)

    try:
        cosmos_client.delete_item("photos", photo_id, photo_id)
    except Exception as exc:
        logging.error("Cosmos delete failed: %s", exc)
        return auth_helper.make_response({"error": "Failed to delete photo record"}, 500)

    return func.HttpResponse(status_code=204, headers=auth_helper.CORS_HEADERS)
