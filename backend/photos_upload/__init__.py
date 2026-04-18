"""
POST /api/photos/upload  — creator only

Accepts multipart/form-data with:
  photo     : image file (required)
  title     : string (required)
  caption   : string
  location  : string
  people    : comma-separated names

Uploads the image to Blob Storage, runs Azure Computer Vision analysis,
then persists a photo document in Cosmos DB.
"""

import cgi
import io
import json
import logging
import uuid
from datetime import datetime, timezone

import azure.functions as func
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import auth_helper, blob_client, cosmos_client, cognitive_service

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _parse_multipart(req: func.HttpRequest) -> cgi.FieldStorage:
    content_type = req.headers.get("Content-Type", "")
    body = req.get_body()
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body)),
    }
    return cgi.FieldStorage(fp=io.BytesIO(body), environ=environ, keep_blank_values=True)


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("photos_upload triggered")

    # Auth — creator only
    try:
        principal = auth_helper.require_role(req, "creator")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(principal)
    user_email = auth_helper.get_user_email(principal)

    # Parse multipart form data
    try:
        form = _parse_multipart(req)
    except Exception as exc:
        logging.error("Multipart parse error: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Invalid multipart form data"}),
            status_code=400, mimetype="application/json",
        )

    # Validate required fields
    title = form.getvalue("title", "").strip()
    if not title:
        return func.HttpResponse(
            json.dumps({"error": "title is required"}),
            status_code=400, mimetype="application/json",
        )

    photo_field = form["photo"] if "photo" in form else None
    if photo_field is None or not hasattr(photo_field, "file"):
        return func.HttpResponse(
            json.dumps({"error": "photo file is required"}),
            status_code=400, mimetype="application/json",
        )

    # Detect MIME type
    content_type = photo_field.type or "image/jpeg"
    if content_type not in _ALLOWED_MIME:
        return func.HttpResponse(
            json.dumps({"error": f"Unsupported file type: {content_type}"}),
            status_code=400, mimetype="application/json",
        )

    image_bytes = photo_field.file.read()
    if len(image_bytes) == 0:
        return func.HttpResponse(
            json.dumps({"error": "Photo file is empty"}),
            status_code=400, mimetype="application/json",
        )

    # Extract optional metadata
    caption = form.getvalue("caption", "").strip()
    location = form.getvalue("location", "").strip()
    people_raw = form.getvalue("people", "")
    people = [p.strip() for p in people_raw.split(",") if p.strip()]

    # Upload to Blob Storage
    photo_id = str(uuid.uuid4())
    blob_name = f"{photo_id}{_EXT_MAP.get(content_type, '.jpg')}"

    try:
        image_url = blob_client.upload_photo(blob_name, image_bytes, content_type)
    except Exception as exc:
        logging.error("Blob upload failed: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Failed to upload image"}),
            status_code=500, mimetype="application/json",
        )

    # Azure Computer Vision analysis (graceful — empty if not configured)
    ai_result = cognitive_service.analyse_image(image_bytes)

    # Persist photo document in Cosmos DB
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": photo_id,
        "uploadedBy": user_id,
        "uploaderEmail": user_email,
        "title": title,
        "caption": caption,
        "location": location,
        "people": people,
        "blobName": blob_name,
        "imageUrl": image_url,
        "avgRating": 0.0,
        "ratingCount": 0,
        "aiTags": ai_result.get("tags", []),
        "aiDescription": ai_result.get("description", ""),
        "aiText": ai_result.get("text", []),
        "createdAt": now,
        "updatedAt": now,
    }

    try:
        cosmos_client.create_item("photos", doc)
    except Exception as exc:
        logging.error("Cosmos DB insert failed: %s", exc)
        # Attempt to clean up orphaned blob
        try:
            blob_client.delete_photo(blob_name)
        except Exception:
            pass
        return func.HttpResponse(
            json.dumps({"error": "Failed to save photo metadata"}),
            status_code=500, mimetype="application/json",
        )

    logging.info("Photo uploaded: %s by %s", photo_id, user_id)
    return func.HttpResponse(
        json.dumps({
            "id": photo_id,
            "imageUrl": image_url,
            "title": title,
            "aiTags": ai_result.get("tags", []),
        }),
        status_code=201,
        mimetype="application/json",
    )
