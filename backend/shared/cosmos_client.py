"""
Reusable Azure Cosmos DB connection helper.
One CosmosClient instance is reused across warm invocations (module-level singleton).
"""

import logging
import os
from typing import Any, Optional

from azure.cosmos import CosmosClient, PartitionKey, exceptions

_client: Optional[CosmosClient] = None
_database = None


def get_database():
    global _client, _database
    if _database is None:
        conn_str = os.environ["COSMOS_DB_CONNECTION_STRING"]
        db_name = os.environ.get("COSMOS_DB_DATABASE_NAME", "photoshare")
        logging.info("cosmos_client: connecting to database=%s", db_name)
        _client = CosmosClient.from_connection_string(conn_str)
        _database = _client.get_database_client(db_name)
        logging.info("cosmos_client: database client ready")
    return _database


def get_container(container_name: str):
    return get_database().get_container_client(container_name)


# ── Convenience wrappers ──────────────────────────────────────────────────────

def create_item(container_name: str, item: dict) -> dict:
    return get_container(container_name).create_item(body=item)


def upsert_item(container_name: str, item: dict) -> dict:
    return get_container(container_name).upsert_item(body=item)


def get_item(container_name: str, item_id: str, partition_key: Any) -> Optional[dict]:
    try:
        return get_container(container_name).read_item(item=item_id, partition_key=partition_key)
    except exceptions.CosmosResourceNotFoundError:
        return None


def delete_item(container_name: str, item_id: str, partition_key: Any) -> None:
    try:
        get_container(container_name).delete_item(item=item_id, partition_key=partition_key)
    except exceptions.CosmosResourceNotFoundError:
        pass


def query_items(container_name: str, query: str, parameters: Optional[list] = None) -> list:
    container = get_container(container_name)
    items = container.query_items(
        query=query,
        parameters=parameters or [],
        enable_cross_partition_query=True,
    )
    return list(items)


def ensure_container(container_name: str, partition_key_path: str) -> None:
    get_database().create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path=partition_key_path),
    )
