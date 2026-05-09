import logging

from app.event_engine import process_valid_event


logger = logging.getLogger("event-engine-core.handlers")


def handle_valid_event(event: dict) -> None:
    logger.info("Received valid event from Kafka: %s", event)
    result = process_valid_event(event)
    logger.info(
        "Event processing result: status=%s; id=%s; event_id=%s; event_hash=%s",
        result["status"],
        result["id"],
        result.get("event_id"),
        result.get("event_hash"),
    )
