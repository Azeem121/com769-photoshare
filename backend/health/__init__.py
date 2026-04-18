import logging
from datetime import datetime, timezone

import azure.functions as func

from shared import auth_helper


def main(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return auth_helper.options_response()

    logging.info("Health check requested")
    return auth_helper.make_response({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    })
