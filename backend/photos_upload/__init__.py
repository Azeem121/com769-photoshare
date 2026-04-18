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
import logging
import traceback
import uuid
from datetime import datetime, timezone

import azure.functions as func

from shared import auth_helper, blob_client, cognitive_service, cosmos_client

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
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    logging.info("photos_upload triggered")

    try:
        user = auth_helper.require_role(req, "creator")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(user)
    username = auth_helper.get_username(user)
    logging.info("photos_upload: user=%s", username)

    # ── Parse multipart form ──────────────────────────────────────────────────
    try:
        form = _parse_multipart(req)
    except Exception:
        logging.exception("Multipart parse error")
        return auth_helper.make_response({"error": "Invalid multipart form data"}, 400)

    title = form.getvalue("title", "").strip()
    if not title:
        return auth_helper.make_response({"error": "title is required"}, 400)

    photo_field = form["photo"] if "photo" in form else None
    if photo_field is None or not hasattr(photo_field, "file"):
        return auth_helper.make_response({"error": "photo file is required"}, 400)

    content_type = photo_field.type or "image/jpeg"
    if content_type not in _ALLOWED_MIME:
        return auth_helper.make_response({"error": f"Unsupported file type: {content_type}"}, 400)

    image_bytes = photo_field.file.read()
    if len(image_bytes) == 0:
        return auth_helper.make_response({"error": "Photo file is empty"}, 400)

    logging.info("photos_upload: file size=%d content_type=%s", len(image_bytes), content_type)

    caption = form.getvalue("caption", "").strip()
    location = form.getvalue("location", "").strip()
    people_raw = form.getvalue("people", "")
    people = [p.strip() for p in people_raw.split(",") if p.strip()]

    # ── Upload to Blob Storage ────────────────────────────────────────────────
    photo_id = str(uuid.uuid4())
    blob_name = f"{photo_id}{_EXT_MAP.get(content_type, '.jpg')}"

    try:
        image_url = blob_client.upload_photo(blob_name, image_bytes, content_type)
        logging.info("photos_upload: blob uploaded url=%s", image_url)
    except Exception as exc:
        logging.exception("Blob upload failed")
        return auth_helper.make_response({
            "error": "Failed to upload image",
            "detail": str(exc),
            "type": type(exc).__name__,
        }, 500)

    # ── Computer Vision (graceful — never blocks upload) ─────────────────────
    try:
        ai_result = cognitive_service.analyse_image(image_bytes)
    except Exception:
        logging.exception("CV analysis raised unexpectedly; continuing with empty tags")
        ai_result = {"tags": [], "description": "", "text": []}

    # ── Save photo document to Cosmos DB ─────────────────────────────────────
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": photo_id,
        "uploadedBy": user_id,
        "uploaderName": username,
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
        logging.info("photos_upload: cosmos doc created id=%s", photo_id)
    except Exception as exc:
        logging.exception("Cosmos DB insert failed; cleaning up blob")
        try:
            blob_client.delete_photo(blob_name)
        except Exception:
            pass
        return auth_helper.make_response({
            "error": "Failed to save photo metadata",
            "detail": str(exc),
            "type": type(exc).__name__,
            "trace": traceback.format_exc(),
        }, 500)

    return auth_helper.make_response({
        "id": photo_id,
        "imageUrl": image_url,
        "title": title,
        "aiTags": ai_result.get("tags", []),
    }, 201)
