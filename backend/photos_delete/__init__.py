"""
DELETE /api/photos/{id}  — creator only, must own the photo

Deletes the Cosmos DB document and the corresponding Blob Storage file.
Comments and ratings for the photo are left in place (orphan cleanup is out
of scope for this assignment).
"""

import json
import logging

import azure.functions as func

from shared import auth_helper, blob_client, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    photo_id = req.route_params.get("id", "")
    logging.info("photos_delete triggered for id=%s", photo_id)

    try:
        principal = auth_helper.require_role(req, "creator")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(principal)

    # Find the photo (cross-partition query since we only know the photo id)
    query = "SELECT * FROM c WHERE c.id = @id"
    params = [{"name": "@id", "value": photo_id}]

    try:
        results = cosmos_client.query_items("photos", query, params)
    except Exception as exc:
        logging.error("Cosmos query failed: %s", exc)
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

    # Ownership check
    if photo.get("uploadedBy") != user_id:
        return func.HttpResponse(
            json.dumps({"error": "You can only delete your own photos"}),
            status_code=403, mimetype="application/json",
        )

    # Delete blob from storage
    blob_name = photo.get("blobName", "")
    if blob_name:
        try:
            blob_client.delete_photo(blob_name)
        except Exception as exc:
            logging.warning("Blob delete failed (continuing): %s", exc)

    # Delete Cosmos DB document (partition key = uploadedBy)
    try:
        cosmos_client.delete_item("photos", photo_id, user_id)
    except Exception as exc:
        logging.error("Cosmos delete failed: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Failed to delete photo record"}),
            status_code=500, mimetype="application/json",
        )

    return func.HttpResponse(status_code=204)
