import json
import logging
import azure.functions as func

# TODO Phase 2: Implement login + JWT issuance


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("users_login triggered")
    return func.HttpResponse(
        json.dumps({"message": "Not yet implemented"}),
        status_code=501,
        mimetype="application/json",
    )
