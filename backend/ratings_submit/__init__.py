"""
POST /api/photos/{id}/rate  — consumer only

Body (JSON):
  rating : integer 1–5 (required)

One rating per user per photo — subsequent calls update the existing rating.
After upserting the rating document, the function recalculates and stores
avgRating and ratingCount on the photo document.
"""

import logging
from datetime import datetime, timezone

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    photo_id = req.route_params.get("id", "")
    logging.info("ratings_submit triggered for photo_id=%s", photo_id)

    try:
        user = auth_helper.require_role(req, "consumer")
    except PermissionError as exc:
        return auth_helper.json_403(str(exc))

    user_id = auth_helper.get_user_id(user)

    try:
        body = req.get_json()
    except ValueError:
        return auth_helper.make_response({"error": "Request body must be JSON"}, 400)

    try:
        rating_value = int(body.get("rating", 0))
    except (TypeError, ValueError):
        rating_value = 0

    if rating_value < 1 or rating_value > 5:
        return auth_helper.make_response({"error": "rating must be an integer between 1 and 5"}, 400)

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
        return auth_helper.make_response({"error": "Failed to save rating"}, 500)

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

    return auth_helper.make_response({"avgRating": avg, "ratingCount": count, "yourRating": rating_value})
