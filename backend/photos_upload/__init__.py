import io
import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone

import azure.functions as func

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
}


def _json(body: dict, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(body), status_code=status,
        mimetype="application/json", headers=CORS,
    )


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=200, headers=CORS)

    logging.info("Step 1: photos_upload started")

    try:
        # Step 2: auth header
        logging.info("Step 2: checking auth header")
        auth_header = req.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _json({"error": "Unauthorized"}, 401)
        token = auth_header.split(" ", 1)[1].strip()

        # Step 3: validate token via cross-partition query (works regardless of partition key)
        logging.info("Step 3: validating token in Cosmos DB")
        from azure.cosmos import CosmosClient
        conn_str = os.environ.get("COSMOS_DB_CONNECTION_STRING", "")
        db_name = os.environ.get("COSMOS_DB_DATABASE_NAME", "photoshare")
        cosmos = CosmosClient.from_connection_string(conn_str)
        db = cosmos.get_database_client(db_name)
        tokens_container = db.get_container_client("tokens")

        items = list(tokens_container.query_items(
            query="SELECT * FROM c WHERE c.id = @token",
            parameters=[{"name": "@token", "value": token}],
            enable_cross_partition_query=True,
        ))
        if not items:
            return _json({"error": "Invalid or expired token"}, 401)

        token_doc = items[0]
        username = token_doc.get("username", "")
        role = token_doc.get("role", "")
        logging.info("Step 3 done: user=%s role=%s", username, role)

        if role != "creator":
            return _json({"error": "Creator role required"}, 403)

        # Step 4: parse form fields
        logging.info("Step 4: parsing form fields")
        title = (req.form.get("title") or "Untitled").strip()
        caption = (req.form.get("caption") or "").strip()
        location = (req.form.get("location") or "").strip()
        people_str = req.form.get("people") or ""
        people = [p.strip() for p in people_str.split(",") if p.strip()]
        logging.info("Step 4 done: title=%s", title)

        # Step 5: read file
        logging.info("Step 5: reading uploaded file")
        photo_file = req.files.get("photo")
        if not photo_file:
            return _json({"error": "No photo file provided"}, 400)
        file_bytes = photo_file.read()
        content_type = photo_file.content_type or "image/jpeg"
        logging.info("Step 5 done: size=%d content_type=%s", len(file_bytes), content_type)

        if not file_bytes:
            return _json({"error": "Photo file is empty"}, 400)

        # Step 6: upload to blob storage
        logging.info("Step 6: uploading to blob storage")
        from azure.storage.blob import BlobServiceClient, ContentSettings
        blob_conn_str = os.environ.get("BLOB_STORAGE_CONNECTION_STRING", "")
        container_name = os.environ.get("BLOB_CONTAINER_NAME", "photos")

        blob_service = BlobServiceClient.from_connection_string(blob_conn_str)
        ext = ".jpg"
        if content_type == "image/png":
            ext = ".png"
        elif content_type == "image/gif":
            ext = ".gif"
        elif content_type == "image/webp":
            ext = ".webp"

        filename = f"{uuid.uuid4()}{ext}"
        blob = blob_service.get_blob_client(container=container_name, blob=filename)
        blob.upload_blob(
            file_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        account_name = blob_service.account_name
        image_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{filename}"
        logging.info("Step 6 done: url=%s", image_url)

        # Step 7: AI tags (optional — never blocks upload)
        logging.info("Step 7: computer vision analysis")
        ai_tags = []
        ai_caption = ""
        try:
            cv_endpoint = os.environ.get("CV_ENDPOINT", "")
            cv_key = os.environ.get("CV_KEY", "")
            if cv_endpoint and cv_key:
                from azure.cognitiveservices.vision.computervision import ComputerVisionClient
                from msrest.authentication import CognitiveServicesCredentials
                cv_client = ComputerVisionClient(
                    cv_endpoint, CognitiveServicesCredentials(cv_key)
                )
                analysis = cv_client.analyze_image_in_stream(
                    io.BytesIO(file_bytes),
                    visual_features=["Tags", "Description"],
                )
                ai_tags = [t.name for t in (analysis.tags or [])[:5] if t.confidence > 0.6]
                if analysis.description and analysis.description.captions:
                    ai_caption = analysis.description.captions[0].text
                logging.info("Step 7 done: tags=%s", ai_tags)
            else:
                logging.info("Step 7: CV not configured, skipping")
        except Exception as cv_err:
            logging.warning("Step 7: CV failed (non-fatal): %s", cv_err)

        # Step 8: save to Cosmos DB
        logging.info("Step 8: saving photo document to Cosmos DB")
        photo_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        photo_doc = {
            "id": photo_id,
            "uploadedBy": username,
            "uploaderName": username,
            "title": title,
            "caption": caption,
            "location": location,
            "people": people,
            "imageUrl": image_url,
            "blobName": filename,
            "aiTags": ai_tags,
            "aiDescription": ai_caption,
            "avgRating": 0.0,
            "ratingCount": 0,
            "createdAt": now,
            "updatedAt": now,
        }

        photos_container = db.get_container_client("photos")
        photos_container.create_item(body=photo_doc)
        logging.info("Step 8 done: photo id=%s saved", photo_id)

        return _json({
            "id": photo_id,
            "imageUrl": image_url,
            "title": title,
            "aiTags": ai_tags,
        }, 201)

    except Exception as exc:
        logging.error("UPLOAD FAILED: %s", traceback.format_exc())
        return _json({"error": str(exc), "trace": traceback.format_exc()}, 500)
