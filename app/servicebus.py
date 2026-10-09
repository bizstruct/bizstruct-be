import asyncio

import structlog

from bizstruct_domain import QueueMessage

from app.core.config import settings

logger = structlog.get_logger(__name__)


def _send_to_queue(message_body: str) -> None:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage

    with ServiceBusClient.from_connection_string(settings.service_bus_connection_string) as client:
        with client.get_queue_sender(settings.service_bus_queue_name) as sender:
            sender.send_messages(ServiceBusMessage(message_body))


class ServiceBusQueue:
    """
        QueuePort over Azure Service Bus. With no connection string configured
        every call is a logged no-op, so local runs and tests never touch Azure.
    """

    async def enqueue(self, message: QueueMessage) -> None:
        target = message.targets[0]
        if not settings.service_bus_connection_string:
            logger.warning(
                "servicebus.enqueue_skipped",
                reason="SERVICE_BUS_CONNECTION_STRING not set",
                project_id=message.project_id,
                stage_row_id=target.stage_row_id,
            )
            return
        # The Azure SDK is blocking; keep it off the event loop.
        await asyncio.to_thread(_send_to_queue, message.model_dump_json())
        logger.info(
            "servicebus.enqueued",
            project_id=message.project_id,
            stage=target.stage.value,
            stage_row_id=target.stage_row_id,
            attempt_id=target.attempt_id,
        )

    async def request_cancellation(self, *, project_id: str, stage_row_id: str) -> None:
        logger.info("servicebus.cancellation_not_sent", project_id=project_id, stage_row_id=stage_row_id)
