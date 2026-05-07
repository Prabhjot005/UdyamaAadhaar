import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from app.kafka.handlers import handle_valid_department_record


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


MessageHandler = Callable[[dict], None]


@dataclass(frozen=True)
class KafkaSubscription:
    topic: str
    group_id: str
    handler: MessageHandler


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap_servers: str
    kafka_subscriptions: list[KafkaSubscription]


settings = Settings(
    kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
    kafka_subscriptions=[
        KafkaSubscription(
            topic=os.getenv("KAFKA_VALID_DEPARTMENT_RECORDS_TOPIC", "valid_department_records"),
            group_id=os.getenv(
                "KAFKA_VALID_DEPARTMENT_RECORDS_GROUP_ID",
                "ubid_engine_valid_department_records_test1",
            ),
            handler=handle_valid_department_record,
        )
    ],
)
