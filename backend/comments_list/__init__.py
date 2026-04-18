import json
import logging
import azure.functions as func

# TODO Phase 2: Query comments container by postId


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("comments_list triggered")
    return func.HttpResponse(
        json.dumps({"message": "Not yet implemented"}),
        status_code=501,
        mimetype="application/json",
    )
