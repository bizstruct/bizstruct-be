import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> Any:
    global _client
    if _client is None:
        from azure.messaging.webpubsubservice import WebPubSubServiceClient
        _client = WebPubSubServiceClient.from_connection_string(
            settings.azure_web_pubsub_connection_string,
            hub=settings.azure_web_pubsub_hub,
        )
    return _client


def get_negotiate_url(project_id: str) -> str:
    client = _get_client()
    token = client.get_client_access_token(groups=[project_id])
    return token["url"]


def send_block_ready(project_id: str, block: str, status: str) -> None:
    if not settings.azure_web_pubsub_connection_string:
        return
    try:
        _get_client().send_to_group(
            group=project_id,
            message=json.dumps({"type": "block_ready", "block": block, "status": status}),
            content_type="application/json",
        )
    except Exception:
        logger.exception("Failed to send block_ready for project %s block %s", project_id, block)


def send_generation_complete(project_id: str, final_status: str) -> None:
    if not settings.azure_web_pubsub_connection_string:
        return
    try:
        _get_client().send_to_group(
            group=project_id,
            message=json.dumps({
                "type": "generation_complete",
                "project_id": project_id,
                "status": final_status,
            }),
            content_type="application/json",
        )
    except Exception:
        logger.exception("Failed to send generation_complete for project %s", project_id)
