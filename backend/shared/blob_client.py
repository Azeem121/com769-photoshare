"""
Azure Blob Storage helper.
Returns direct public blob URLs (or CDN URL when CDN_ENDPOINT_URL is set).
"""

import logging
import os

from azure.storage.blob import BlobServiceClient, ContentSettings


def _get_service() -> BlobServiceClient:
    conn_str = os.environ.get("BLOB_STORAGE_CONNECTION_STRING", "")
    if not conn_str:
        raise RuntimeError("BLOB_STORAGE_CONNECTION_STRING env var is not set")
    return BlobServiceClient.from_connection_string(conn_str)


def upload_photo(blob_name: str, data: bytes, content_type: str) -> str:
    """Upload bytes to Blob Storage and return the public URL."""
    container_name = os.environ.get("BLOB_CONTAINER_NAME", "photos")
    logging.info("blob_client: uploading %s to container=%s", blob_name, container_name)

    service = _get_service()
    blob = service.get_blob_client(container=container_name, blob=blob_name)

    blob.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )

    # Build the URL explicitly from account name (reliable, no SAS tokens)
    account_name = service.account_name
    cdn_base = os.environ.get("CDN_ENDPOINT_URL", "").rstrip("/")
    if cdn_base:
        url = f"{cdn_base}/{container_name}/{blob_name}"
    else:
        url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"

    logging.info("blob_client: upload done url=%s", url)
    return url


def delete_photo(blob_name: str) -> None:
    container_name = os.environ.get("BLOB_CONTAINER_NAME", "photos")
    service = _get_service()
    blob = service.get_blob_client(container=container_name, blob=blob_name)
    blob.delete_blob(delete_snapshots="include")
    logging.info("blob_client: deleted %s", blob_name)
