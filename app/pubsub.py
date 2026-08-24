import json
import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

_client = None


def _parse_conn_str(conn_str: str) -> tuple[str, str]:
    """Extract endpoint and access_key from an Azure connection string."""
    parts: dict[str, str] = {}
    for segment in conn_str.rstrip(";").split(";"):
        if "=" in segment:
            k, _, v = segment.partition("=")
            parts[k.strip().lower()] = v.strip()
    return parts.get("endpoint", ""), parts.get("accesskey", "")


def _make_client() -> Any:
    from azure.core.credentials import AzureKeyCredential
    from azure.messaging.webpubsubservice import WebPubSubServiceClient

    endpoint, access_key = _parse_conn_str(settings.azure_web_pubsub_connection_string)
    client = WebPubSubServiceClient(
        endpoint=endpoint,
        hub=settings.azure_web_pubsub_hub,
        credential=AzureKeyCredential(access_key),
    )
    # SDK bug: _base_url="{endpoint}" but path_format_arguments passes "Endpoint" (capital E).
    # Python str.format() is case-sensitive → KeyError. Fix: resolve the template immediately.
    client._client._base_url = endpoint
    return client


def _get_client() -> Any:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


def get_negotiate_url(project_id: str) -> str:
    token = _get_client().get_client_access_token(groups=[project_id])
    # Azure returns wss:// for WebSocket; EventSource requires https://
    url: str = token["url"]
    return url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)


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


def send_validate_result(project_id: str, model_id: str, result: dict) -> None:
    if not settings.azure_web_pubsub_connection_string:
        return
    try:
        _get_client().send_to_group(
            group=project_id,
            message=json.dumps({
                "type": "validate_model_result",
                "model_id": model_id,
                "result": result,
            }),
            content_type="application/json",
        )
    except Exception:
        logger.exception("Failed to send validate_result for project %s model %s", project_id, model_id)


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
