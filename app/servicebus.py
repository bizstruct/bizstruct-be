import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def enqueue_block(project_id: str, block: str) -> None:
    """Put a generation task on the Service Bus queue. No-op if not configured."""
    if not settings.service_bus_connection_string:
        logger.warning("SERVICE_BUS_CONNECTION_STRING not set — skipping enqueue for %s/%s", project_id, block)
        return

    from azure.servicebus import ServiceBusClient, ServiceBusMessage

    message_body = json.dumps({"project_id": project_id, "block": block})
    try:
        with ServiceBusClient.from_connection_string(settings.service_bus_connection_string) as client:
            with client.get_queue_sender(settings.service_bus_queue_name) as sender:
                sender.send_messages(ServiceBusMessage(message_body))
        logger.info("Enqueued block %s for project %s", block, project_id)
    except Exception:
        logger.exception("Failed to enqueue block %s for project %s", block, project_id)
        raise
