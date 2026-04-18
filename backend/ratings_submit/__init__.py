"""
POST /api/photos/{id}/rate  — consumer only

Body (JSON):
  rating : integer 1–5 (required)

One rating per user per photo — subsequent calls update the existing rating.
After upserting the rating document, the function recalculates and stores
avgRating and ratingCount on the photo document.
"""

import json
import logging
from datetime import datetime, timezone

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    photo_id = req.route_params.get("id", "")
    logging.info("ratings_submit triggered for photo_id=%s", photo_id)

    try:
        principal = auth_helper.require_role(req, "consumer")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(principal)

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Request body must be JSON"}),
            status_code=400, mimetype="application/json",
        )

    try:
        rating_value = int(body.get("rating", 0))
    except (TypeError, ValueError):
        rating_value = 0

    if rating_value < 1 or rating_value > 5:
        return func.HttpResponse(
            json.dumps({"error": "rating must be an integer between 1 and 5"}),
            status_code=400, mimetype="application/json",
        )

    # Upsert rating document  (id = userId_photoId ensures one-per-user-per-photo)
    now = datetime.now(timezone.utc).isoformat()
    rating_doc = {
        "id": f"{user_id}_{photo_id}",
        "photoId": photo_id,
        "userId": user_id,
        "rating": rating_value,
        "updatedAt": now,
    }

    try:
        cosmos_client.upsert_item("ratings", rating_doc)
    except Exception as exc:
        logging.error("Failed to upsert rating: %s", exc)
        return func.HttpResponse(
            json.dumps({"error": "Failed to save rating"}),
            status_code=500, mimetype="application/json",
        )

    # Recalculate aggregate rating for the photo
    agg_query = """
        SELECT VALUE {
            "count": COUNT(1),
            "sum": SUM(c.rating)
        }
        FROM c
        WHERE c.photoId = @photoId
    """
    agg_params = [{"name": "@photoId", "value": photo_id}]

    try:
        agg_results = cosmos_client.query_items("ratings", agg_query, agg_params)
        agg = agg_results[0] if agg_results else {"count": 1, "sum": rating_value}
        count = agg.get("count", 1)
        total = agg.get("sum", rating_value)
        avg = round(total / count, 2) if count > 0 else 0.0
    except Exception as exc:
        logging.warning("Aggregate query failed; using estimate: %s", exc)
        count, avg = 1, float(rating_value)

    # Patch the photo document with updated averages
    # Fetch photo first (cross-partition)
    photo_query = "SELECT * FROM c WHERE c.id = @id"
    photo_params = [{"name": "@id", "value": photo_id}]
    try:
        photos = cosmos_client.query_items("photos", photo_query, photo_params)
        if photos:
            photo = photos[0]
            photo["avgRating"] = avg
            photo["ratingCount"] = count
            cosmos_client.upsert_item("photos", photo)
    except Exception as exc:
        logging.warning("Failed to update photo averages: %s", exc)

    return func.HttpResponse(
        json.dumps({"avgRating": avg, "ratingCount": count, "yourRating": rating_value}),
        status_code=200,
        mimetype="application/json",
    )
