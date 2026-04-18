"""
Azure Computer Vision helper (free tier: 5 000 calls / month).

Environment variables required:
    CV_ENDPOINT  - e.g. https://eastus.api.cognitive.microsoft.com/
    CV_KEY       - subscription key

If either variable is missing the function degrades gracefully and returns
an empty result so photo upload still works without Cognitive Services.
"""

import io
import logging
import os
from typing import Optional

try:
    from azure.cognitiveservices.vision.computervision import ComputerVisionClient
    from azure.cognitiveservices.vision.computervision.models import VisualFeatureTypes
    from msrest.authentication import CognitiveServicesCredentials
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False
    logging.warning("azure-cognitiveservices-vision-computervision not installed; AI analysis disabled")

_cv_client: Optional[object] = None


def _get_client():
    global _cv_client
    if _cv_client is None and _SDK_AVAILABLE:
        endpoint = os.environ.get("CV_ENDPOINT", "")
        key = os.environ.get("CV_KEY", "")
        if endpoint and key:
            _cv_client = ComputerVisionClient(
                endpoint, CognitiveServicesCredentials(key)
            )
    return _cv_client


def analyse_image(image_bytes: bytes) -> dict:
    """
    Send image bytes to Azure Computer Vision and return a dict with:
      - tags: list[str]       auto-detected labels (confidence > 0.6)
      - description: str      best auto-caption
      - text: list[str]       OCR-detected text lines

    Returns empty structure if CV is not configured or call fails.
    """
    empty = {"tags": [], "description": "", "text": []}
    client = _get_client()
    if client is None:
        return empty

    try:
        stream = io.BytesIO(image_bytes)

        features = [
            VisualFeatureTypes.tags,
            VisualFeatureTypes.description,
        ]
        analysis = client.analyze_image_in_stream(stream, visual_features=features)

        tags = [
            t.name
            for t in (analysis.tags or [])
            if t.confidence and t.confidence > 0.6
        ]

        description = ""
        if analysis.description and analysis.description.captions:
            description = analysis.description.captions[0].text

        # OCR via read_in_stream (async operation)
        ocr_lines = _extract_ocr_text(client, image_bytes)

        return {"tags": tags, "description": description, "text": ocr_lines}

    except Exception as exc:
        logging.warning("Computer Vision analysis failed: %s", exc)
        return empty


def _extract_ocr_text(client, image_bytes: bytes) -> list:
    """Run the Read OCR operation and collect text lines."""
    try:
        import time
        stream = io.BytesIO(image_bytes)
        read_response = client.read_in_stream(stream, raw=True)
        operation_id = read_response.headers["Operation-Location"].split("/")[-1]

        # Poll until done (max 10 seconds for free tier)
        for _ in range(10):
            result = client.get_read_result(operation_id)
            if result.status not in ("notStarted", "running"):
                break
            time.sleep(1)

        lines = []
        if result.status == "succeeded":
            for page in result.analyze_result.read_results:
                for line in page.lines:
                    lines.append(line.text)
        return lines
    except Exception as exc:
        logging.warning("OCR extraction failed: %s", exc)
        return []
