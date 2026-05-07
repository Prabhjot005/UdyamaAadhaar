from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

import uvicorn

from app.config import settings
from app.kafka.consumer_manager import KafkaConsumerManager

logging.basicConfig(level=logging.INFO)

kafka_consumer_manager = KafkaConsumerManager(settings.kafka_subscriptions)


@asynccontextmanager
async def lifespan(app: FastAPI):
    kafka_consumer_manager.start()
    yield
    kafka_consumer_manager.stop()


app = FastAPI(title="UBID Engine Core Service", lifespan=lifespan)


@app.get("/")
def greet():
    return {"message": "UBID Engine Core Service"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "kafka_topics": [subscription.topic for subscription in settings.kafka_subscriptions],
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
