"""
GET /api/photos  — public

Query parameters:
  search  : keyword matched against title, caption, location, people
  sort    : "recent" (default) | "rating"
  tag     : filter by a single AI tag (exact match)
  page    : 1-based page number (default 1)
  limit   : items per page (default 12, max 50)
"""

import logging

import azure.functions as func

from shared import auth_helper, cosmos_client


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    logging.info("photos_list triggered")

    search = req.params.get("search", "").strip()
    sort = req.params.get("sort", "recent").strip().lower()
    tag = req.params.get("tag", "").strip()

    try:
        page = max(1, int(req.params.get("page", "1")))
        limit = min(50, max(1, int(req.params.get("limit", "12"))))
    except ValueError:
        page, limit = 1, 12

    offset = (page - 1) * limit

    conditions = []
    parameters = []

    if search:
        conditions.append(
            "(CONTAINS(LOWER(c.title), LOWER(@search)) OR "
            "CONTAINS(LOWER(c.caption), LOWER(@search)) OR "
            "CONTAINS(LOWER(c.location), LOWER(@search)) OR "
            "EXISTS(SELECT VALUE p FROM p IN c.people WHERE CONTAINS(LOWER(p), LOWER(@search))))"
        )
        parameters.append({"name": "@search", "value": search})

    if tag:
        conditions.append("ARRAY_CONTAINS(c.aiTags, @tag)")
        parameters.append({"name": "@tag", "value": tag})

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    order_clause = "ORDER BY c.createdAt DESC" if sort != "rating" else "ORDER BY c.avgRating DESC"

    query = f"""
        SELECT c.id, c.title, c.caption, c.location, c.people,
               c.imageUrl, c.uploaderName, c.avgRating, c.ratingCount,
               c.aiTags, c.aiDescription, c.createdAt
        FROM c
        {where_clause}
        {order_clause}
        OFFSET {offset} LIMIT {limit}
    """

    try:
        photos = cosmos_client.query_items("photos", query, parameters)
    except Exception as exc:
        logging.error("Cosmos DB query failed: %s", exc)
        return auth_helper.make_response({"error": "Failed to retrieve photos"}, 500)

    count_query = f"SELECT VALUE COUNT(1) FROM c {where_clause}"
    try:
        count_result = cosmos_client.query_items("photos", count_query, parameters)
        total = count_result[0] if count_result else 0
    except Exception:
        total = len(photos)

    return auth_helper.make_response({
        "photos": photos,
        "total": total,
        "page": page,
        "limit": limit,
    })
