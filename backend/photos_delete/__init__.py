"""
DELETE /api/photos/{id}  — creator only, must own the photo

Deletes the Cosmos DB document and the corresponding Blob Storage file.
Comments and ratings for the photo are left in place (orphan cleanup is out
of scope for this assignment).
"""

import logging

import azure.functions as func

from shared import auth_helper, blob_client, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    photo_id = req.route_params.get("id", "")
    logging.info("photos_delete triggered for id=%s", photo_id)

    try:
        user = auth_helper.require_role(req, "creator")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(user)

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

    if photo.get("uploadedBy") != user_id:
        return auth_helper.make_response({"error": "You can only delete your own photos"}, 403)

    blob_name = photo.get("blobName", "")
    if blob_name:
        try:
            blob_client.delete_photo(blob_name)
        except Exception as exc:
            logging.warning("Blob delete failed (continuing): %s", exc)

    try:
        cosmos_client.delete_item("photos", photo_id, user_id)
    except Exception as exc:
        logging.error("Cosmos delete failed: %s", exc)
        return auth_helper.make_response({"error": "Failed to delete photo record"}, 500)

    return func.HttpResponse(status_code=204, headers=auth_helper.CORS_HEADERS)
