from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

import uvicorn

from app.config import settings
from app.decision_engine import (
    ReviewResolutionRequest,
    fetch_ubid_master,
    fetch_reviews,
    initialize_decision_engine_storage,
    resolve_review,
)
from app.kafka.consumer_manager import KafkaConsumerManager

logging.basicConfig(level=logging.INFO)

kafka_consumer_manager = KafkaConsumerManager(settings.kafka_subscriptions)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_decision_engine_storage()
    kafka_consumer_manager.start()
    yield
    kafka_consumer_manager.stop()


app = FastAPI(title="UBID Engine Core Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def greet():
    return {"message": "UBID Engine Core Service is running!"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "kafka_topics": [subscription.topic for subscription in settings.kafka_subscriptions],
    }


@app.get("/reviews")
def get_reviews(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    confidence: str | None = Query(default=None),
    match_confidence: str | None = Query(default=None),
    min_match_score: float | None = Query(default=None),
    max_match_score: float | None = Query(default=None),
):
    return {
        "reviews": fetch_reviews(
            status=status,
            search=search,
            match_confidence=match_confidence or confidence,
            min_match_score=min_match_score,
            max_match_score=max_match_score,
        )
    }


@app.post("/resolve/review/{review_id}")
def resolve_review_api(review_id: str, request: ReviewResolutionRequest):
    try:
        return resolve_review(review_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/ubids")
def get_ubids(
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    source_system: str | None = Query(default=None),
):
    return fetch_ubid_master(search=search, status=status, source_system=source_system)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
