"""
POST /api/photos/upload  — creator only

Accepts multipart/form-data with:
  photo     : image file (required)
  title     : string (required)
  caption   : string
  location  : string
  people    : comma-separated names
"""

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


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    logging.info("photos_upload triggered")

    try:
        # Step 1 — auth
        logging.info("Step 1: checking auth")
        try:
            user = auth_helper.require_role(req, "creator")
        except PermissionError as exc:
            return auth_helper.json_403(str(exc))

        user_id = auth_helper.get_user_id(user)
        username = auth_helper.get_username(user)
        logging.info("Step 1 done: user=%s", username)

        # Step 2 — parse form
        logging.info("Step 2: parsing form fields")
        title = (req.form.get("title") or "").strip()
        if not title:
            return auth_helper.make_response({"error": "title is required"}, 400)

        photo_file = req.files.get("photo")
        if not photo_file:
            return auth_helper.make_response({"error": "photo file is required"}, 400)

        content_type = photo_file.content_type or "image/jpeg"
        if content_type not in _ALLOWED_MIME:
            return auth_helper.make_response(
                {"error": f"Unsupported file type: {content_type}"}, 400
            )

        # Step 3 — read file bytes
        logging.info("Step 3: reading file bytes")
        image_bytes = photo_file.read()
        if not image_bytes:
            return auth_helper.make_response({"error": "Photo file is empty"}, 400)
        logging.info("Step 3 done: size=%d content_type=%s", len(image_bytes), content_type)

        caption = (req.form.get("caption") or "").strip()
        location = (req.form.get("location") or "").strip()
        people_raw = req.form.get("people") or ""
        people = [p.strip() for p in people_raw.split(",") if p.strip()]

        # Step 4 — upload to blob storage
        photo_id = str(uuid.uuid4())
        blob_name = f"{photo_id}{_EXT_MAP.get(content_type, '.jpg')}"
        logging.info("Step 4: uploading to blob storage blob_name=%s", blob_name)

        try:
            image_url = blob_client.upload_photo(blob_name, image_bytes, content_type)
        except Exception as exc:
            logging.exception("Step 4 FAILED: blob upload error")
            return auth_helper.make_response({
                "error": "Failed to upload image",
                "detail": str(exc),
                "type": type(exc).__name__,
            }, 500)
        logging.info("Step 4 done: url=%s", image_url)

        # Step 5 — computer vision (optional, never blocks)
        logging.info("Step 5: running computer vision")
        try:
            ai_result = cognitive_service.analyse_image(image_bytes)
        except Exception:
            logging.exception("Step 5: CV failed, continuing with empty tags")
            ai_result = {"tags": [], "description": "", "text": []}
        logging.info("Step 5 done: tags=%s", ai_result.get("tags", []))

        # Step 6 — save to Cosmos DB
        logging.info("Step 6: saving to Cosmos DB")
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
        except Exception as exc:
            logging.exception("Step 6 FAILED: Cosmos DB insert error")
            try:
                blob_client.delete_photo(blob_name)
            except Exception:
                pass
            return auth_helper.make_response({
                "error": "Failed to save photo metadata",
                "detail": str(exc),
                "type": type(exc).__name__,
            }, 500)

        logging.info("Step 6 done: photo id=%s saved successfully", photo_id)

        return auth_helper.make_response({
            "id": photo_id,
            "imageUrl": image_url,
            "title": title,
            "aiTags": ai_result.get("tags", []),
        }, 201)

    except Exception as exc:
        logging.error("Unhandled upload error: %s", traceback.format_exc())
        return auth_helper.make_response({
            "error": str(exc),
            "trace": traceback.format_exc(),
        }, 500)
