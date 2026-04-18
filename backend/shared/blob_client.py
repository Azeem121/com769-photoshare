"""
Azure Blob Storage helper with optional CDN URL rewriting.

When CDN_ENDPOINT_URL is set (e.g. https://cdnep-scalableapp.azureedge.net),
public photo URLs are served through the CDN edge rather than directly from
blob storage.  Cache-Control headers are set on upload so the CDN respects TTL.
"""

import logging
import os
from typing import Optional

from azure.storage.blob import BlobServiceClient, ContentSettings

_blob_service: Optional[BlobServiceClient] = None

# 7-day browser + CDN cache for immutable photo blobs
_PHOTO_CACHE_CONTROL = "public, max-age=604800, immutable"


def get_blob_service() -> BlobServiceClient:
    global _blob_service
    if _blob_service is None:
        conn_str = os.environ["BLOB_STORAGE_CONNECTION_STRING"]
        logging.info("blob_client: initialising BlobServiceClient")
        _blob_service = BlobServiceClient.from_connection_string(conn_str)
    return _blob_service


def get_container_client():
    container_name = os.environ.get("BLOB_CONTAINER_NAME", "photos")
    logging.info("blob_client: using container=%s", container_name)
    return get_blob_service().get_container_client(container_name)


def _cdn_url(blob_url: str, blob_name: str) -> str:
    cdn_base = os.environ.get("CDN_ENDPOINT_URL", "").rstrip("/")
    if not cdn_base:
        return blob_url
    container_name = os.environ.get("BLOB_CONTAINER_NAME", "photos")
    return f"{cdn_base}/{container_name}/{blob_name}"


def upload_photo(blob_name: str, data: bytes, content_type: str) -> str:
    container = get_container_client()
    blob = container.get_blob_client(blob_name)
    blob.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(
            content_type=content_type,
            cache_control=_PHOTO_CACHE_CONTROL,
        ),
    )
    url = _cdn_url(blob.url, blob_name)
    logging.info("blob_client: uploaded %s -> %s", blob_name, url)
    return url


def delete_photo(blob_name: str) -> None:
    container = get_container_client()
    blob = container.get_blob_client(blob_name)
    blob.delete_blob(delete_snapshots="include")
    logging.info("blob_client: deleted blob %s", blob_name)
