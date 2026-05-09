from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import settings
from app.event_engine import (
    fetch_event_category_computations,
    fetch_event_reviews,
    fetch_event_stats,
    fetch_events,
    fetch_ubid_statuses,
    initialize_event_engine_storage,
    resolve_event_review,
    EventReviewResolutionRequest,
)
from app.kafka.consumer_manager import KafkaConsumerManager


logging.basicConfig(level=logging.INFO)

kafka_consumer_manager = KafkaConsumerManager(settings.kafka_subscriptions)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_event_engine_storage()
    kafka_consumer_manager.start()
    yield
    kafka_consumer_manager.stop()


app = FastAPI(title="Event Engine Core Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3003", "http://127.0.0.1:3003"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def greet():
    return {"message": "Event Engine Core Service is running!"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "kafka_topics": [subscription.topic for subscription in settings.kafka_subscriptions],
    }


@app.get("/events")
def get_events(
    event_type: str | None = Query(default=None),
    ubid: str | None = Query(default=None),
    source_name: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    return {
        "events": fetch_events(
            event_type=event_type,
            ubid=ubid,
            source_name=source_name,
            search=search,
            limit=limit,
        )
    }


@app.get("/events/stats")
def get_event_stats():
    return fetch_event_stats()


@app.get("/events/reviews")
def get_event_reviews(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    return {"reviews": fetch_event_reviews(status=status, search=search, limit=limit)}


@app.post("/events/reviews/{review_id}/resolve")
def resolve_event_review_api(review_id: str, request: EventReviewResolutionRequest):
    try:
        return resolve_event_review(review_id, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/events/computations")
def get_event_category_computations(
    ubid: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
):
    return {"computations": fetch_event_category_computations(ubid=ubid, limit=limit)}


@app.get("/ubid-status")
def get_ubid_statuses(
    ubid: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
):
    return {"statuses": fetch_ubid_statuses(ubid=ubid, active_only=active_only, limit=limit)}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8008, reload=True)
