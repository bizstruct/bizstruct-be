import asyncio
import logging
from typing import Any

from bizstruct_domain import StageEvent

from app.core.config import settings

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


class WebPubSubEvents:
    """
        EventPort over Azure Web PubSub: sends the domain StageEvent to the
        project's group. A no-op while no connection string is configured, and
        a failed send is logged, never raised.
    """

    async def publish(self, event: StageEvent) -> None:
        if not settings.azure_web_pubsub_connection_string:
            return
        try:
            await asyncio.to_thread(
                _get_client().send_to_group,
                group=event.project_id,
                message=event.model_dump_json(),
                content_type="application/json",
            )
        except Exception:
            logger.exception(
                "Failed to send stage event for project %s row %s", event.project_id, event.stage_row_id
            )
