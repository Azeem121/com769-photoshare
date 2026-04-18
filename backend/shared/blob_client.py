"""
Azure Blob Storage helper with optional CDN URL rewriting.

When CDN_ENDPOINT_URL is set (e.g. https://cdnep-scalableapp.azureedge.net),
public photo URLs are served through the CDN edge rather than directly from
blob storage.  Cache-Control headers are set on upload so the CDN respects TTL.
"""

import os
import logging
from typing import Optional

from azure.storage.blob import BlobServiceClient, ContentSettings

_blob_service: Optional[BlobServiceClient] = None

# 7-day browser + CDN cache for immutable photo blobs
_PHOTO_CACHE_CONTROL = "public, max-age=604800, immutable"


def get_blob_service() -> BlobServiceClient:
    global _blob_service
    if _blob_service is None:
        conn_str = os.environ["BLOB_STORAGE_CONNECTION_STRING"]
        _blob_service = BlobServiceClient.from_connection_string(conn_str)
    return _blob_service


def get_container_client():
    container_name = os.environ["BLOB_CONTAINER_NAME"]
    return get_blob_service().get_container_client(container_name)


def _cdn_url(blob_url: str, blob_name: str) -> str:
    """
    Replace the blob storage hostname with the CDN endpoint hostname so that
    all public photo links are served through the CDN cache layer.
    """
    cdn_base = os.environ.get("CDN_ENDPOINT_URL", "").rstrip("/")
    if not cdn_base:
        return blob_url
    container_name = os.environ["BLOB_CONTAINER_NAME"]
    return f"{cdn_base}/{container_name}/{blob_name}"


def upload_photo(blob_name: str, data: bytes, content_type: str) -> str:
    """
    Upload photo bytes to Blob Storage and return the public URL.
    The URL is the CDN URL when CDN_ENDPOINT_URL is configured, otherwise
    the raw blob URL.
    """
    container = get_container_client()
    blob_client = container.get_blob_client(blob_name)
    blob_client.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(
            content_type=content_type,
            cache_control=_PHOTO_CACHE_CONTROL,
        ),
    )
    return _cdn_url(blob_client.url, blob_name)


def delete_photo(blob_name: str) -> None:
    container = get_container_client()
    blob_client = container.get_blob_client(blob_name)
    blob_client.delete_blob(delete_snapshots="include")
    logging.info("Deleted blob: %s", blob_name)
