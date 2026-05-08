import json
import logging
import threading
from dataclasses import dataclass

from confluent_kafka import Consumer, KafkaException

from app.config import KafkaSubscription, settings


logger = logging.getLogger("ubid-engine-core.kafka")


@dataclass
class ConsumerWorker:
    subscription: KafkaSubscription
    shutdown_event: threading.Event
    thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self._consume,
            name=f"kafka-consumer-{self.subscription.topic}",
            daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        if self.thread:
            self.thread.join(timeout=10)

    def _build_consumer(self) -> Consumer:
        return Consumer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "group.id": self.subscription.group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )

    def _consume(self) -> None:
        consumer = self._build_consumer()
        consumer.subscribe([self.subscription.topic])
        logger.info(
            "Subscribed to Kafka topic '%s' with group '%s'",
            self.subscription.topic,
            self.subscription.group_id,
        )

        try:
            while not self.shutdown_event.is_set():
                message = consumer.poll(timeout=1.0)

                if message is None:
                    continue

                if message.error():
                    logger.error("Kafka consumer error: %s", message.error())
                    continue

                try:
                    payload = message.value().decode("utf-8")
                    record = json.loads(payload)
                    self.subscription.handler(record)
                except json.JSONDecodeError:
                    logger.exception("Invalid JSON received from topic '%s'", self.subscription.topic)
                except Exception:
                    logger.exception("Failed to process Kafka message from topic '%s'", self.subscription.topic)
        except KafkaException:
            logger.exception("Kafka consumer stopped due to Kafka exception")
        finally:
            consumer.close()
            logger.info("Kafka consumer for topic '%s' closed", self.subscription.topic)


class KafkaConsumerManager:
    def __init__(self, subscriptions: list[KafkaSubscription]):
        self.shutdown_event = threading.Event()
        self.workers = [
            ConsumerWorker(subscription=subscription, shutdown_event=self.shutdown_event)
            for subscription in subscriptions
        ]

    def start(self) -> None:
        self.shutdown_event.clear()
        for worker in self.workers:
            worker.start()
        logger.info("Started %s Kafka consumer worker(s)", len(self.workers))

    def stop(self) -> None:
        self.shutdown_event.set()
        for worker in self.workers:
            worker.stop()
        logger.info("Stopped Kafka consumer workers")
