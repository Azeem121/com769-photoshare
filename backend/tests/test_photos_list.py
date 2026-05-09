"""
Unit tests for photos_list — verifies pagination, filtering and error handling
without a real Cosmos DB connection.
"""

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the real photos_list module (shared/ is importable from backend/)
import photos_list as pl_module  # noqa: E402

SAMPLE_PHOTOS = [
    {
        "id": "abc123",
        "title": "Mountain Sunrise",
        "caption": "Beautiful dawn",
        "location": "Alps",
        "people": [],
        "imageUrl": "https://example.com/img.jpg",
        "uploaderName": "mike",
        "avgRating": 4.5,
        "ratingCount": 2,
        "aiTags": ["mountain", "sunrise"],
        "aiDescription": "Mountain at sunrise",
        "createdAt": "2026-05-01T00:00:00+00:00",
    }
]


class _FakeRequest:
    def __init__(self, params=None, method="GET"):
        self.params = params or {}
        self.method = method
        self.headers = {}


def _call(photos=None, total=None, params=None, method="GET"):
    """Run main() with mocked cosmos and auth, return captured body/status."""
    photo_list = photos if photos is not None else SAMPLE_PHOTOS
    count = total if total is not None else len(photo_list)
    captured = {}

    with patch.object(pl_module, "cosmos_client") as mock_cosmos, \
         patch.object(pl_module, "auth_helper") as mock_auth:

        mock_cosmos.query_items.side_effect = [photo_list, [count]]

        def fake_response(body, status_code=200, **kw):
            captured["body"] = body
            captured["status"] = status_code
            return MagicMock(status_code=status_code)

        mock_auth.make_response.side_effect = fake_response
        mock_auth.options_response.return_value = MagicMock(status_code=200)

        pl_module.main(_FakeRequest(params=params, method=method))

    return captured, mock_auth


def test_returns_photos_list():
    captured, _ = _call()
    assert "photos" in captured["body"]
    assert captured["body"]["photos"] == SAMPLE_PHOTOS
    assert captured["status"] == 200


def test_total_from_count_query():
    captured, _ = _call(total=42)
    assert captured["body"]["total"] == 42


def test_default_pagination():
    captured, _ = _call()
    assert captured["body"]["page"] == 1
    assert captured["body"]["limit"] == 12


def test_empty_photos():
    captured, _ = _call(photos=[], total=0)
    assert captured["body"]["photos"] == []
    assert captured["body"]["total"] == 0


def test_options_returns_cors():
    _, mock_auth = _call(method="OPTIONS")
    mock_auth.options_response.assert_called_once()


def test_cosmos_error_returns_500():
    captured = {}
    with patch.object(pl_module, "cosmos_client") as mock_cosmos, \
         patch.object(pl_module, "auth_helper") as mock_auth:

        mock_cosmos.query_items.side_effect = Exception("Cosmos unavailable")

        def fake_response(body, status_code=200, **kw):
            captured["body"] = body
            captured["status"] = status_code
            return MagicMock(status_code=status_code)

        mock_auth.make_response.side_effect = fake_response
        mock_auth.options_response.return_value = MagicMock(status_code=200)

        pl_module.main(_FakeRequest())

    assert captured["status"] == 500
    assert "error" in captured["body"]
