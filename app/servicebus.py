import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def _send_to_queue(message_body: str) -> None:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage

    with ServiceBusClient.from_connection_string(settings.service_bus_connection_string) as client:
        with client.get_queue_sender(settings.service_bus_queue_name) as sender:
            sender.send_messages(ServiceBusMessage(message_body))


def enqueue_block(project_id: str, block: str) -> None:
    if not settings.service_bus_connection_string:
        logger.warning("SERVICE_BUS_CONNECTION_STRING not set — skipping enqueue for %s/%s", project_id, block)
        return
    message_body = json.dumps({"project_id": project_id, "block": block})
    try:
        _send_to_queue(message_body)
        logger.info("Enqueued block %s for project %s", block, project_id)
    except Exception:
        logger.exception("Failed to enqueue block %s for project %s", block, project_id)
        raise


def enqueue_validate(project_id: str, model_id: str, model_data: dict) -> None:
    if not settings.service_bus_connection_string:
        logger.warning("SERVICE_BUS_CONNECTION_STRING not set — skipping validate enqueue for %s", project_id)
        return
    message_body = json.dumps({
        "project_id": project_id,
        "block": "validate_model",
        "payload": {"model_id": model_id, **model_data},
    })
    try:
        _send_to_queue(message_body)
        logger.info("Enqueued validate_model for project %s model %s", project_id, model_id)
    except Exception:
        logger.exception("Failed to enqueue validate_model for project %s", project_id)
        raise
