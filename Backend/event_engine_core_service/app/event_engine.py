import json
import logging
import math
import os
import uuid
from datetime import date, datetime
from functools import lru_cache
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from pydantic import BaseModel


logger = logging.getLogger("event-engine-core.event-engine")


class EventReviewResolutionRequest(BaseModel):
    ubid: str
    remarks: str | None = None


def _postgres_host() -> str:
    return os.getenv("POSTGRES_HOST", "localhost")


def _postgres_port() -> str:
    return os.getenv("POSTGRES_PORT", "5432")


def _postgres_db() -> str:
    return os.getenv("POSTGRES_DB", "udyama")


def _postgres_user() -> str:
    return os.getenv("POSTGRES_USER", "admin")


def _postgres_password() -> str:
    return os.getenv("POSTGRES_PASSWORD", "admin")


def _ubid_match_api_url() -> str:
    return os.getenv("UBID_MATCH_API_URL", "http://localhost:8006/ubids/match")


def _event_category_match_api_url() -> str:
    return os.getenv("EVENT_CATEGORY_MATCH_API_URL", "http://localhost:8006/event-categories/match")


def _event_value(event: dict, key: str) -> str:
    return str(event.get(key) or "")


def _json_dumps(value) -> str:
    return json.dumps(value, default=str)


def _json_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _iso_datetime(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _generate_review_id() -> str:
    return f"EVREV-{uuid.uuid4().hex[:12].upper()}"


def _first_value(*values) -> str:
    for value in values:
        if value not in (None, "", []):
            return str(value)
    return ""


def _additional_properties(event: dict) -> dict:
    value = event.get("additionalProperties") or event.get("additional_properties") or {}
    return value if isinstance(value, dict) else {}


def _additional_value(event: dict, *keys: str) -> str:
    additional = _additional_properties(event)
    for key in keys:
        if additional.get(key) not in (None, "", []):
            return str(additional.get(key))
    return ""


def _ubid_match_payload(event: dict) -> dict[str, Any]:
    pan = _first_value(event.get("pan"), event.get("panNumber"), _additional_value(event, "pan", "panNumber", "pan_number"))
    source_type = _first_value(
        event.get("sourceType"),
        event.get("sourceName"),
        event.get("kafkaTopic"),
        _additional_value(event, "sourceType", "source_type", "sourceName", "source_name", "sourceSystem", "source_system", "source"),
    )

    return {
        "gstin": _first_value(event.get("gstin"), _additional_value(event, "gstin")),
        "pan": pan,
        "departmentRecordId": _first_value(event.get("departmentRecordId"), _additional_value(event, "departmentRecordId", "department_record_id", "deptRecordId", "dept_record_id")),
        "sourceType": source_type,
        "name": _first_value(event.get("name"), _additional_value(event, "name", "businessName", "business_name", "entityName", "entity_name")),
        "address": _first_value(event.get("address"), _additional_value(event, "address", "otherAddress", "other_address")),
        "pincode": _first_value(event.get("pincode"), _additional_value(event, "pincode", "pinCode", "pin_code", "postalCode", "postal_code")),
        "limit": 5,
    }


def _event_supplied_ubid(event: dict) -> str:
    return _first_value(event.get("ubid"), _additional_value(event, "ubid"))


def _preassigned_ubid_match_response(ubid: str, payload: dict[str, Any]) -> dict[str, Any]:
    top_match = {
        "ubid": ubid,
        "record_id": None,
        "data_record_id": None,
        "match_type": "hard",
        "matched_field": "ubid",
        "similarity_score": 1.0,
        "matched_record": None,
        "metadata": {"source": "event_payload"},
    }
    return {
        "status": "UBID_MATCHED",
        "matched_ubid": ubid,
        "top_match": top_match,
        "matches": [top_match],
        "input": payload,
        "thresholds": {
            "candidate_match_min_score": 0.7,
            "auto_match_min_score": 0.9,
        },
        "stored": False,
    }


def _event_category_match_payload(event: dict) -> dict[str, Any]:
    additional = _additional_properties(event)
    event_type_details = additional.get("eventTypeDetails") or additional.get("event_type_details") or {}
    if not isinstance(event_type_details, dict):
        event_type_details = {}
    event_category = _first_value(
        event.get("eventCategory"),
        event_type_details.get("category"),
        event_type_details.get("eventCategory"),
        event_type_details.get("name"),
        additional.get("eventCategory"),
        additional.get("event_category"),
        additional.get("category"),
        event.get("eventType"),
    )
    description = _first_value(
        event.get("description"),
        event.get("eventDescription"),
        event.get("descriptiveVectorText"),
        event_type_details.get("description"),
        event_type_details.get("eventDescription"),
        event_type_details.get("descriptiveVectorText"),
        additional.get("description"),
        additional.get("eventDescription"),
        additional.get("event_description"),
        additional.get("descriptiveVectorText"),
        additional.get("descriptive_vector_text"),
    )
    if not description:
        description = " ".join(
            str(value)
            for value in [
                event.get("eventType"),
                event.get("name"),
                event.get("sourceName"),
                json.dumps(additional, default=str, sort_keys=True) if additional else "",
            ]
            if value not in (None, "", [], {})
        )

    return {
        "eventCategory": event_category,
        "descriptiveVectorText": description or event_category,
    }


def _call_ubid_match_api(payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    logger.info("Calling UBID match API: url=%s payload=%s", _ubid_match_api_url(), payload)
    api_request = urlrequest.Request(
        _ubid_match_api_url(),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlrequest.urlopen(api_request, timeout=30) as response:
            match_response = json.loads(response.read().decode("utf-8"))
            logger.info(
                "UBID match API response received: status_code=%s decision_status=%s matched_ubid=%s match_count=%s",
                response.status,
                match_response.get("status"),
                match_response.get("matched_ubid"),
                len(match_response.get("matches") or []),
            )
            return match_response
    except urlerror.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "UBID match API returned HTTP error: status_code=%s reason=%s details=%s",
            exc.code,
            exc.reason,
            details,
        )
        return {
            "status": "MATCH_API_ERROR",
            "matched_ubid": None,
            "top_match": None,
            "matches": [],
            "error": {
                "type": "HTTPError",
                "status_code": exc.code,
                "reason": exc.reason,
                "details": details,
                "url": _ubid_match_api_url(),
            },
            "input": payload,
            "stored": False,
        }
    except urlerror.URLError as exc:
        logger.error("UBID match API connection failed: reason=%s url=%s", exc.reason, _ubid_match_api_url())
        return {
            "status": "MATCH_API_ERROR",
            "matched_ubid": None,
            "top_match": None,
            "matches": [],
            "error": {
                "type": "URLError",
                "reason": str(exc.reason),
                "url": _ubid_match_api_url(),
            },
            "input": payload,
            "stored": False,
        }


def _call_event_category_match_api(payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    logger.info("Calling event category match API: url=%s payload=%s", _event_category_match_api_url(), payload)
    api_request = urlrequest.Request(
        _event_category_match_api_url(),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlrequest.urlopen(api_request, timeout=30) as response:
            match_response = json.loads(response.read().decode("utf-8"))
            if not isinstance(match_response, dict):
                logger.error(
                    "Event category match API returned no match: status_code=%s payload=%s",
                    response.status,
                    match_response,
                )
                return {
                    "status": "CATEGORY_MATCH_NOT_FOUND",
                    "error": {
                        "type": "NoMatch",
                        "details": "Event category master returned no candidate match.",
                        "url": _event_category_match_api_url(),
                    },
                    "input": payload,
                }
            logger.info(
                "Event category match API response received: status_code=%s category_id=%s score=%s base_weight=%s decay=%s",
                response.status,
                match_response.get("category_id"),
                match_response.get("similarity_score"),
                match_response.get("base_weight"),
                match_response.get("recommended_decay_constant"),
            )
            return match_response
    except urlerror.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        logger.error(
            "Event category match API returned HTTP error: status_code=%s reason=%s details=%s",
            exc.code,
            exc.reason,
            details,
        )
        return {
            "status": "CATEGORY_MATCH_API_ERROR",
            "error": {
                "type": "HTTPError",
                "status_code": exc.code,
                "reason": exc.reason,
                "details": details,
                "url": _event_category_match_api_url(),
            },
            "input": payload,
        }
    except urlerror.URLError as exc:
        logger.error("Event category match API connection failed: reason=%s url=%s", exc.reason, _event_category_match_api_url())
        return {
            "status": "CATEGORY_MATCH_API_ERROR",
            "error": {
                "type": "URLError",
                "reason": str(exc.reason),
                "url": _event_category_match_api_url(),
            },
            "input": payload,
        }


def _top_match(match_response: dict) -> dict | None:
    top_match = match_response.get("top_match")
    return top_match if isinstance(top_match, dict) else None


def _decision_values(match_response: dict) -> tuple[str, str | None, str | None]:
    if match_response.get("status") == "MATCH_API_ERROR":
        error = match_response.get("error") or {}
        return "MATCH_LOOKUP_FAILED", None, f"UBID match API call failed: {error}"

    top_match = _top_match(match_response)
    if not top_match:
        return "NO_MATCH", None, None

    matched_ubid = top_match.get("ubid") or match_response.get("matched_ubid")
    match_type = top_match.get("match_type")
    score = float(top_match.get("similarity_score") or 0)
    thresholds = match_response.get("thresholds") or {}
    candidate_threshold = float(thresholds.get("candidate_match_min_score") or 0.7)
    auto_threshold = float(thresholds.get("auto_match_min_score") or 0.9)

    if match_type == "hard" or score > auto_threshold:
        return "UBID_MATCHED", matched_ubid, "Matched by hard key or exceeded auto-match threshold."

    if match_type == "vector" and matched_ubid and score < auto_threshold:
        return "REVIEW_REQUIRED", matched_ubid, "Vector candidate below auto-match threshold requires review."

    if score >= candidate_threshold:
        return "REVIEW_REQUIRED", matched_ubid, "Candidate match requires review."

    return "NO_MATCH", None, "Top candidate was below candidate-match threshold."


def _should_process_event_category(decision_status: str, matched_ubid: str | None) -> bool:
    return bool(matched_ubid) and decision_status == "UBID_MATCHED"


def _run_status_inference_flow(
    cursor,
    incoming_event_id: int,
    decision_id: int,
    event: dict,
    ubid: str,
    trigger: str,
) -> dict[str, Any] | None:
    category_payload = _event_category_match_payload(event)
    logger.info(
        "Processing event status inference flow: trigger=%s event_id=%s ubid=%s category_payload=%s",
        trigger,
        _event_value(event, "eventId"),
        ubid,
        category_payload,
    )
    category_match = _call_event_category_match_api(category_payload)
    category_result = _store_event_category_match_and_compute(
        cursor=cursor,
        incoming_event_id=incoming_event_id,
        decision_id=decision_id,
        event=event,
        ubid=ubid,
        category_payload=category_payload,
        category_match=category_match,
    )
    logger.info(
        "Event status inference flow completed: trigger=%s event_id=%s ubid=%s category_result=%s",
        trigger,
        _event_value(event, "eventId"),
        ubid,
        category_result,
    )
    return category_result


@lru_cache(maxsize=1)
def _get_connection():
    import psycopg2

    connection = psycopg2.connect(
        host=_postgres_host(),
        port=_postgres_port(),
        dbname=_postgres_db(),
        user=_postgres_user(),
        password=_postgres_password(),
    )
    connection.autocommit = False
    _ensure_tables(connection)
    return connection


def _ensure_tables(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incoming_events (
                id BIGSERIAL PRIMARY KEY,
                event_id VARCHAR(128),
                mongo_id VARCHAR(128),
                event_hash VARCHAR(128),
                event_type VARCHAR(128),
                gstin VARCHAR(32),
                pan VARCHAR(16),
                ubid VARCHAR(64),
                department_record_id VARCHAR(128),
                source_name VARCHAR(128),
                name TEXT,
                address TEXT,
                pincode VARCHAR(16),
                raw_event JSONB NOT NULL,
                additional_properties JSONB NOT NULL DEFAULT '{}'::jsonb,
                kafka_topic VARCHAR(128),
                validation_created_at TIMESTAMPTZ,
                validation_updated_at TIMESTAMPTZ,
                processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS event_review_master (
                review_id VARCHAR(64) PRIMARY KEY,
                incoming_event_id BIGINT NOT NULL REFERENCES incoming_events(id),
                event_id VARCHAR(128),
                suggested_ubid VARCHAR(64),
                status VARCHAR(64) NOT NULL,
                resolved_ubid VARCHAR(64),
                remarks TEXT,
                top_similarity_score DOUBLE PRECISION,
                top_match_type VARCHAR(64),
                top_match_record_id VARCHAR(128),
                raw_event JSONB NOT NULL,
                match_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                match_response JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                resolved_at TIMESTAMPTZ
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS event_decisions (
                id BIGSERIAL PRIMARY KEY,
                incoming_event_id BIGINT NOT NULL REFERENCES incoming_events(id),
                event_id VARCHAR(128),
                decision_status VARCHAR(64) NOT NULL,
                matched_ubid VARCHAR(64),
                review_id VARCHAR(64),
                top_similarity_score DOUBLE PRECISION,
                top_match_type VARCHAR(64),
                top_match_record_id VARCHAR(128),
                decision_reason TEXT NOT NULL,
                match_payload JSONB NOT NULL,
                match_response JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS event_decision_candidates (
                id BIGSERIAL PRIMARY KEY,
                decision_id BIGINT NOT NULL REFERENCES event_decisions(id),
                review_id VARCHAR(64),
                rank INTEGER NOT NULL,
                ubid VARCHAR(64),
                record_id VARCHAR(128),
                data_record_id VARCHAR(128),
                match_type VARCHAR(64),
                matched_field VARCHAR(64),
                similarity_score DOUBLE PRECISION,
                candidate_status VARCHAR(64) NOT NULL DEFAULT 'RECORDED',
                matched_record JSONB,
                metadata JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS event_category_matches (
                id BIGSERIAL PRIMARY KEY,
                incoming_event_id BIGINT NOT NULL REFERENCES incoming_events(id),
                decision_id BIGINT REFERENCES event_decisions(id),
                event_id VARCHAR(128),
                ubid VARCHAR(64),
                event_category_id VARCHAR(128),
                event_category VARCHAR(128),
                event_description TEXT,
                similarity_score DOUBLE PRECISION,
                base_weight DOUBLE PRECISION,
                recommended_decay_constant DOUBLE PRECISION,
                match_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                match_response JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS event_ubid_events_computation (
                id BIGSERIAL PRIMARY KEY,
                ubid VARCHAR(64) NOT NULL,
                event_category_id VARCHAR(128) NOT NULL,
                event_category VARCHAR(128),
                latest_event_id VARCHAR(128),
                base_weight DOUBLE PRECISION NOT NULL,
                final_decay_constant DOUBLE PRECISION NOT NULL,
                multiplication_decay_constant_factor DOUBLE PRECISION NOT NULL,
                score DOUBLE PRECISION NOT NULL,
                last_computed_date DATE NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (ubid, event_category_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ubid_status (
                id BIGSERIAL PRIMARY KEY,
                ubid VARCHAR(64) NOT NULL,
                computed_positive_score DOUBLE PRECISION NOT NULL,
                computed_negative_score DOUBLE PRECISION NOT NULL,
                status VARCHAR(64) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                latest_event_id VARCHAR(128),
                event_computation_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                deactivated_at TIMESTAMPTZ
            )
            """
        )
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS event_id VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS mongo_id VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS event_hash VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS event_type VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS gstin VARCHAR(32)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS pan VARCHAR(16)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS ubid VARCHAR(64)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS department_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS source_name VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS name TEXT")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS address TEXT")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS pincode VARCHAR(16)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS raw_event JSONB NOT NULL DEFAULT '{}'::jsonb")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS additional_properties JSONB NOT NULL DEFAULT '{}'::jsonb")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS kafka_topic VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS validation_created_at TIMESTAMPTZ")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS validation_updated_at TIMESTAMPTZ")
        cursor.execute("ALTER TABLE incoming_events ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        cursor.execute("ALTER TABLE event_review_master ADD COLUMN IF NOT EXISTS match_payload JSONB NOT NULL DEFAULT '{}'::jsonb")
        cursor.execute("ALTER TABLE event_review_master ADD COLUMN IF NOT EXISTS resolved_ubid VARCHAR(64)")
        cursor.execute("ALTER TABLE event_review_master ADD COLUMN IF NOT EXISTS remarks TEXT")
        cursor.execute("ALTER TABLE event_decisions ADD COLUMN IF NOT EXISTS match_payload JSONB NOT NULL DEFAULT '{}'::jsonb")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS decision_id BIGINT")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS event_id VARCHAR(128)")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS ubid VARCHAR(64)")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS event_category_id VARCHAR(128)")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS event_category VARCHAR(128)")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS event_description TEXT")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS similarity_score DOUBLE PRECISION")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS base_weight DOUBLE PRECISION")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS recommended_decay_constant DOUBLE PRECISION")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS match_payload JSONB NOT NULL DEFAULT '{}'::jsonb")
        cursor.execute("ALTER TABLE event_category_matches ADD COLUMN IF NOT EXISTS match_response JSONB NOT NULL DEFAULT '{}'::jsonb")
        cursor.execute("ALTER TABLE event_ubid_events_computation ADD COLUMN IF NOT EXISTS latest_event_id VARCHAR(128)")
        cursor.execute("ALTER TABLE event_ubid_events_computation ADD COLUMN IF NOT EXISTS base_weight DOUBLE PRECISION NOT NULL DEFAULT 0")
        cursor.execute("ALTER TABLE event_ubid_events_computation ADD COLUMN IF NOT EXISTS final_decay_constant DOUBLE PRECISION NOT NULL DEFAULT 0")
        cursor.execute("ALTER TABLE event_ubid_events_computation ADD COLUMN IF NOT EXISTS multiplication_decay_constant_factor DOUBLE PRECISION NOT NULL DEFAULT 1")
        cursor.execute("ALTER TABLE event_ubid_events_computation ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION NOT NULL DEFAULT 0")
        cursor.execute("ALTER TABLE event_ubid_events_computation ADD COLUMN IF NOT EXISTS last_computed_date DATE NOT NULL DEFAULT CURRENT_DATE")
        cursor.execute("ALTER TABLE ubid_status ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
        cursor.execute("ALTER TABLE ubid_status ADD COLUMN IF NOT EXISTS latest_event_id VARCHAR(128)")
        cursor.execute("ALTER TABLE ubid_status ADD COLUMN IF NOT EXISTS event_computation_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb")
        cursor.execute("ALTER TABLE ubid_status ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        cursor.execute("ALTER TABLE ubid_status ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMPTZ")
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_incoming_events_event_hash_unique
            ON incoming_events (event_hash)
            WHERE event_hash IS NOT NULL AND event_hash <> ''
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_events_event_id ON incoming_events (event_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_events_event_type ON incoming_events (event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_events_ubid ON incoming_events (ubid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_events_department_record_id ON incoming_events (department_record_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_events_source_name ON incoming_events (source_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_reviews_status ON event_review_master (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_reviews_incoming_event_id ON event_review_master (incoming_event_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_decisions_incoming_event_id ON event_decisions (incoming_event_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_decisions_status ON event_decisions (decision_status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_decisions_matched_ubid ON event_decisions (matched_ubid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_candidates_decision_id ON event_decision_candidates (decision_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_candidates_review_id ON event_decision_candidates (review_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_category_matches_incoming_event_id ON event_category_matches (incoming_event_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_category_matches_ubid ON event_category_matches (ubid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_category_matches_event_category_id ON event_category_matches (event_category_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_computation_ubid ON event_ubid_events_computation (ubid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_computation_ubid_category ON event_ubid_events_computation (ubid, event_category_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ubid_status_ubid_active ON ubid_status (ubid, is_active)")
    connection.commit()


def initialize_event_engine_storage() -> None:
    _get_connection()


def _status_from_scores(positive_score: float, negative_score: float) -> str:
    if negative_score < -6 and positive_score < 5:
        return "INACTIVE"
    if negative_score > -2 and positive_score > 5:
        return "ACTIVE"
    if negative_score > -6 and positive_score < 5:
        return "DORMANT"
    return "DORMANT"


def _decay_existing_scores(cursor, ubid: str, computed_date: date) -> None:
    cursor.execute(
        """
        SELECT id, score, multiplication_decay_constant_factor, last_computed_date
        FROM event_ubid_events_computation
        WHERE ubid = %s
        FOR UPDATE
        """,
        (ubid,),
    )
    rows = cursor.fetchall()
    for row_id, score, decay_factor, last_computed_date in rows:
        delta_days = max((computed_date - last_computed_date).days, 0) if last_computed_date else 0
        decayed_score = float(score or 0) * (float(decay_factor or 1) ** delta_days)
        cursor.execute(
            """
            UPDATE event_ubid_events_computation
            SET score = %s,
                last_computed_date = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (decayed_score, computed_date, row_id),
        )


def _snapshot_computation_rows(cursor, ubid: str) -> tuple[list[dict[str, Any]], float, float]:
    cursor.execute(
        """
        SELECT
            ubid,
            event_category_id,
            event_category,
            latest_event_id,
            base_weight,
            final_decay_constant,
            multiplication_decay_constant_factor,
            score,
            last_computed_date,
            updated_at
        FROM event_ubid_events_computation
        WHERE ubid = %s
        ORDER BY event_category_id
        """,
        (ubid,),
    )
    columns = [description[0] for description in cursor.description]
    snapshot = []
    positive_score = 0.0
    negative_score = 0.0
    for row in cursor.fetchall():
        item = dict(zip(columns, row))
        item["last_computed_date"] = item["last_computed_date"].isoformat() if item["last_computed_date"] else None
        item["updated_at"] = _iso_datetime(item["updated_at"])
        score = float(item["score"] or 0)
        if score >= 0:
            positive_score += score
        else:
            negative_score += score
        snapshot.append(item)

    return snapshot, positive_score, negative_score


def _upsert_ubid_status(
    cursor,
    ubid: str,
    latest_event_id: str,
    snapshot: list[dict[str, Any]],
    positive_score: float,
    negative_score: float,
) -> str:
    new_status = _status_from_scores(positive_score, negative_score)
    cursor.execute(
        """
        SELECT id, status
        FROM ubid_status
        WHERE ubid = %s AND is_active = TRUE
        ORDER BY created_at DESC
        LIMIT 1
        FOR UPDATE
        """,
        (ubid,),
    )
    active_row = cursor.fetchone()

    if active_row and active_row[1] == new_status:
        cursor.execute(
            """
            UPDATE ubid_status
            SET computed_positive_score = %s,
                computed_negative_score = %s,
                latest_event_id = %s,
                event_computation_snapshot = %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (positive_score, negative_score, latest_event_id, _json_dumps(snapshot), active_row[0]),
        )
        return new_status

    if active_row:
        cursor.execute(
            """
            UPDATE ubid_status
            SET is_active = FALSE,
                updated_at = NOW(),
                deactivated_at = NOW()
            WHERE id = %s
            """,
            (active_row[0],),
        )

    cursor.execute(
        """
        INSERT INTO ubid_status (
            ubid,
            computed_positive_score,
            computed_negative_score,
            status,
            is_active,
            latest_event_id,
            event_computation_snapshot
        )
        VALUES (%s, %s, %s, %s, TRUE, %s, %s::jsonb)
        """,
        (ubid, positive_score, negative_score, new_status, latest_event_id, _json_dumps(snapshot)),
    )
    return new_status


def _store_event_category_match_and_compute(
    cursor,
    incoming_event_id: int,
    decision_id: int,
    event: dict,
    ubid: str,
    category_payload: dict[str, Any],
    category_match: dict[str, Any],
) -> dict[str, Any] | None:
    if (
        not isinstance(category_match, dict)
        or category_match.get("status") in {"CATEGORY_MATCH_API_ERROR", "CATEGORY_MATCH_NOT_FOUND"}
        or not category_match.get("category_id")
    ):
        cursor.execute(
            """
            INSERT INTO event_category_matches (
                incoming_event_id,
                decision_id,
                event_id,
                ubid,
                event_description,
                match_payload,
                match_response
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            """,
            (
                incoming_event_id,
                decision_id,
                _event_value(event, "eventId"),
                ubid,
                category_payload.get("descriptiveVectorText"),
                _json_dumps(category_payload),
                _json_dumps(category_match),
            ),
        )
        return None

    category_id = category_match["category_id"]
    event_category = category_match.get("event_category")
    base_weight = float(category_match.get("base_weight") or 0)
    decay_constant = float(category_match.get("recommended_decay_constant") or 0)
    decay_factor = math.exp(-decay_constant)
    event_id = _event_value(event, "eventId")
    computed_date = date.today()

    cursor.execute(
        """
        INSERT INTO event_category_matches (
            incoming_event_id,
            decision_id,
            event_id,
            ubid,
            event_category_id,
            event_category,
            event_description,
            similarity_score,
            base_weight,
            recommended_decay_constant,
            match_payload,
            match_response
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        """,
        (
            incoming_event_id,
            decision_id,
            event_id,
            ubid,
            category_id,
            event_category,
            category_payload.get("descriptiveVectorText"),
            category_match.get("similarity_score"),
            base_weight,
            decay_constant,
            _json_dumps(category_payload),
            _json_dumps(category_match),
        ),
    )

    _decay_existing_scores(cursor, ubid, computed_date)
    cursor.execute(
        """
        SELECT id, score
        FROM event_ubid_events_computation
        WHERE ubid = %s AND event_category_id = %s
        FOR UPDATE
        """,
        (ubid, category_id),
    )
    current_row = cursor.fetchone()

    if current_row:
        new_score = float(current_row[1] or 0) + base_weight
        cursor.execute(
            """
            UPDATE event_ubid_events_computation
            SET event_category = %s,
                latest_event_id = %s,
                base_weight = %s,
                final_decay_constant = %s,
                multiplication_decay_constant_factor = %s,
                score = %s,
                last_computed_date = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (event_category, event_id, base_weight, decay_constant, decay_factor, new_score, computed_date, current_row[0]),
        )
    else:
        new_score = base_weight
        cursor.execute(
            """
            INSERT INTO event_ubid_events_computation (
                ubid,
                event_category_id,
                event_category,
                latest_event_id,
                base_weight,
                final_decay_constant,
                multiplication_decay_constant_factor,
                score,
                last_computed_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (ubid, category_id, event_category, event_id, base_weight, decay_constant, decay_factor, new_score, computed_date),
        )

    snapshot, positive_score, negative_score = _snapshot_computation_rows(cursor, ubid)
    status = _upsert_ubid_status(cursor, ubid, event_id, snapshot, positive_score, negative_score)
    return {
        "event_category_id": category_id,
        "event_category": event_category,
        "base_weight": base_weight,
        "recommended_decay_constant": decay_constant,
        "multiplication_decay_constant_factor": decay_factor,
        "category_score": new_score,
        "computed_positive_score": positive_score,
        "computed_negative_score": negative_score,
        "ubid_status": status,
    }


def process_valid_event(event: dict) -> dict[str, Any]:
    connection = _get_connection()
    event_hash = _event_value(event, "eventHash")

    try:
        with connection.cursor() as cursor:
            if event_hash:
                cursor.execute(
                    "SELECT id, event_id FROM incoming_events WHERE event_hash = %s LIMIT 1",
                    (event_hash,),
                )
                existing = cursor.fetchone()
                if existing:
                    connection.commit()
                    return {
                        "status": "DUPLICATE",
                        "id": existing[0],
                        "event_id": existing[1],
                        "event_hash": event_hash,
                    }

            match_payload = _ubid_match_payload(event)
            supplied_ubid = _event_supplied_ubid(event)
            if supplied_ubid:
                match_response = _preassigned_ubid_match_response(supplied_ubid, match_payload)
                decision_status = "UBID_MATCHED"
                matched_ubid = supplied_ubid
                decision_reason = "UBID was supplied directly in the validated event payload."
            else:
                match_response = _call_ubid_match_api(match_payload)
                decision_status, matched_ubid, decision_reason = _decision_values(match_response)
            top_match = _top_match(match_response)
            review_id = _generate_review_id() if decision_status in {"REVIEW_REQUIRED", "NO_MATCH"} else None
            category_result = None

            cursor.execute(
                """
                INSERT INTO incoming_events (
                    event_id,
                    mongo_id,
                    event_hash,
                    event_type,
                    gstin,
                    pan,
                    ubid,
                    department_record_id,
                    source_name,
                    name,
                    address,
                    pincode,
                    raw_event,
                    additional_properties,
                    kafka_topic,
                    validation_created_at,
                    validation_updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s)
                RETURNING id
                """,
                (
                    _event_value(event, "eventId"),
                    _event_value(event, "mongoId"),
                    event_hash,
                    _event_value(event, "eventType"),
                    _event_value(event, "gstin"),
                    _event_value(event, "pan"),
                    _event_value(event, "ubid"),
                    match_payload.get("departmentRecordId"),
                    match_payload.get("sourceType"),
                    match_payload.get("name"),
                    match_payload.get("address"),
                    match_payload.get("pincode"),
                    _json_dumps(event),
                    _json_dumps(event.get("additionalProperties") or {}),
                    _event_value(event, "kafkaTopic"),
                    event.get("createdAt"),
                    event.get("updatedAt"),
                ),
            )
            incoming_event_id = cursor.fetchone()[0]

            if review_id:
                cursor.execute(
                    """
                    INSERT INTO event_review_master (
                        review_id,
                        incoming_event_id,
                        event_id,
                        suggested_ubid,
                        status,
                        top_similarity_score,
                        top_match_type,
                        top_match_record_id,
                        raw_event,
                        match_payload,
                        match_response
                    )
                    VALUES (%s, %s, %s, %s, 'PENDING_REVIEW', %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                    """,
                    (
                        review_id,
                        incoming_event_id,
                        _event_value(event, "eventId"),
                        matched_ubid,
                        top_match.get("similarity_score") if top_match else None,
                        top_match.get("match_type") if top_match else None,
                        top_match.get("record_id") if top_match else None,
                        _json_dumps(event),
                        _json_dumps(match_payload),
                        _json_dumps(match_response),
                    ),
                )

            cursor.execute(
                """
                INSERT INTO event_decisions (
                    incoming_event_id,
                    event_id,
                    decision_status,
                    matched_ubid,
                    review_id,
                    top_similarity_score,
                    top_match_type,
                    top_match_record_id,
                    decision_reason,
                    match_payload,
                    match_response
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                RETURNING id
                """,
                (
                    incoming_event_id,
                    _event_value(event, "eventId"),
                    decision_status,
                    matched_ubid,
                    review_id,
                    top_match.get("similarity_score") if top_match else None,
                    top_match.get("match_type") if top_match else None,
                    top_match.get("record_id") if top_match else None,
                    decision_reason or "No UBID match found for event.",
                    _json_dumps(match_payload),
                    _json_dumps(match_response),
                ),
            )
            decision_id = cursor.fetchone()[0]

            for index, candidate in enumerate(match_response.get("matches") or [], start=1):
                candidate_status = "PENDING_REVIEW" if review_id else ("SELECTED" if index == 1 and decision_status == "UBID_MATCHED" else "RECORDED")
                cursor.execute(
                    """
                    INSERT INTO event_decision_candidates (
                        decision_id,
                        review_id,
                        rank,
                        ubid,
                        record_id,
                        data_record_id,
                        match_type,
                        matched_field,
                        similarity_score,
                        candidate_status,
                        matched_record,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    """,
                    (
                        decision_id,
                        review_id,
                        index,
                        candidate.get("ubid"),
                        candidate.get("record_id"),
                        candidate.get("data_record_id"),
                        candidate.get("match_type"),
                        candidate.get("matched_field"),
                        candidate.get("similarity_score"),
                        candidate_status,
                        _json_dumps(candidate.get("matched_record")),
                        _json_dumps(candidate.get("metadata") or {}),
                    ),
                )

            logger.info(
                "Event UBID decision completed: event_id=%s decision_status=%s matched_ubid=%s top_score=%s",
                _event_value(event, "eventId"),
                decision_status,
                matched_ubid,
                top_match.get("similarity_score") if top_match else None,
            )

            if _should_process_event_category(decision_status, matched_ubid):
                category_result = _run_status_inference_flow(
                    cursor=cursor,
                    incoming_event_id=incoming_event_id,
                    decision_id=decision_id,
                    event=event,
                    ubid=matched_ubid,
                    trigger=decision_status,
                )
            else:
                logger.info(
                    "Skipping event status inference flow until UBID is finalized: event_id=%s decision_status=%s matched_ubid=%s",
                    _event_value(event, "eventId"),
                    decision_status,
                    matched_ubid,
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {
        "status": decision_status,
        "id": incoming_event_id,
        "event_id": _event_value(event, "eventId"),
        "event_hash": _event_value(event, "eventHash"),
        "matched_ubid": matched_ubid,
        "review_id": review_id,
        "top_similarity_score": top_match.get("similarity_score") if top_match else None,
        "top_match_type": top_match.get("match_type") if top_match else None,
        "event_category_result": category_result,
    }


def fetch_events(
    event_type: str | None = None,
    ubid: str | None = None,
    source_name: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    connection = _get_connection()
    params: list[Any] = []
    filters: list[str] = []

    if event_type:
        filters.append("event_type = %s")
        params.append(event_type)

    if ubid:
        filters.append("ubid = %s")
        params.append(ubid)

    if source_name:
        filters.append("source_name = %s")
        params.append(source_name)

    if search and search.strip():
        filters.append(
            """
            LOWER(
                COALESCE(event_id, '') || ' ' ||
                COALESCE(event_hash, '') || ' ' ||
                COALESCE(event_type, '') || ' ' ||
                COALESCE(gstin, '') || ' ' ||
                COALESCE(pan, '') || ' ' ||
                COALESCE(ubid, '') || ' ' ||
                COALESCE(department_record_id, '') || ' ' ||
                COALESCE(source_name, '') || ' ' ||
                COALESCE(name, '') || ' ' ||
                COALESCE(raw_event::text, '')
            ) LIKE %s
            """
        )
        params.append(f"%{search.strip().lower()}%")

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                event_id,
                mongo_id,
                event_hash,
                event_type,
                gstin,
                pan,
                ubid,
                department_record_id,
                source_name,
                name,
                address,
                pincode,
                raw_event,
                additional_properties,
                kafka_topic,
                validation_created_at,
                validation_updated_at,
                processed_at,
                latest_decision.decision_status,
                latest_decision.matched_ubid,
                latest_decision.review_id,
                latest_decision.top_similarity_score,
                latest_decision.top_match_type
            FROM incoming_events e
            LEFT JOIN LATERAL (
                SELECT
                    d.decision_status,
                    d.matched_ubid,
                    d.review_id,
                    d.top_similarity_score,
                    d.top_match_type
                FROM event_decisions d
                WHERE d.incoming_event_id = e.id
                ORDER BY d.created_at DESC
                LIMIT 1
            ) latest_decision ON TRUE
            {where_clause}
            ORDER BY e.processed_at DESC
            LIMIT %s
            """,
            params,
        )
        columns = [description[0] for description in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    connection.commit()

    for row in rows:
        row["raw_event"] = _json_value(row["raw_event"])
        row["additional_properties"] = _json_value(row["additional_properties"]) or {}
        row["validation_created_at"] = _iso_datetime(row["validation_created_at"])
        row["validation_updated_at"] = _iso_datetime(row["validation_updated_at"])
        row["processed_at"] = _iso_datetime(row["processed_at"])

    return rows


def fetch_event_stats() -> dict[str, Any]:
    connection = _get_connection()

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_events,
                COUNT(*) FILTER (WHERE processed_at::date = CURRENT_DATE) AS processed_today,
                COUNT(DISTINCT event_type) AS event_type_count,
                COUNT(DISTINCT ubid) FILTER (WHERE ubid IS NOT NULL AND ubid <> '') AS ubid_count
            FROM incoming_events
            """
        )
        total_events, processed_today, event_type_count, ubid_count = cursor.fetchone()

        cursor.execute(
            """
            SELECT event_type, COUNT(*) AS count
            FROM incoming_events
            GROUP BY event_type
            ORDER BY count DESC, event_type ASC
            LIMIT 20
            """
        )
        by_event_type = [
            {"event_type": event_type, "count": count}
            for event_type, count in cursor.fetchall()
        ]
    connection.commit()

    return {
        "total_events": total_events,
        "processed_today": processed_today,
        "event_type_count": event_type_count,
        "ubid_count": ubid_count,
        "by_event_type": by_event_type,
    }


def fetch_event_reviews(
    status: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    connection = _get_connection()
    params: list[Any] = []
    filters: list[str] = []

    if status:
        filters.append("rm.status = %s")
        params.append(status)

    if search and search.strip():
        filters.append(
            """
            LOWER(
                COALESCE(rm.review_id, '') || ' ' ||
                COALESCE(rm.event_id, '') || ' ' ||
                COALESCE(rm.suggested_ubid, '') || ' ' ||
                COALESCE(e.event_type, '') || ' ' ||
                COALESCE(e.gstin, '') || ' ' ||
                COALESCE(e.pan, '') || ' ' ||
                COALESCE(e.department_record_id, '') || ' ' ||
                COALESCE(e.source_name, '') || ' ' ||
                COALESCE(e.name, '') || ' ' ||
                COALESCE(rm.raw_event::text, '')
            ) LIKE %s
            """
        )
        params.append(f"%{search.strip().lower()}%")

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                rm.review_id,
                rm.incoming_event_id,
                rm.event_id,
                rm.suggested_ubid,
                rm.status,
                rm.resolved_ubid,
                rm.remarks,
                rm.top_similarity_score,
                rm.top_match_type,
                rm.top_match_record_id,
                rm.raw_event,
                rm.match_payload,
                rm.match_response,
                rm.created_at,
                rm.resolved_at,
                e.event_type,
                e.gstin,
                e.pan,
                e.department_record_id,
                e.source_name,
                e.name,
                e.address,
                e.pincode
            FROM event_review_master rm
            JOIN incoming_events e ON e.id = rm.incoming_event_id
            {where_clause}
            ORDER BY rm.created_at DESC
            LIMIT %s
            """,
            params,
        )
        columns = [description[0] for description in cursor.description]
        reviews = [dict(zip(columns, row)) for row in cursor.fetchall()]

        review_ids = [review["review_id"] for review in reviews]
        candidates_by_review_id: dict[str, list[dict[str, Any]]] = {review_id: [] for review_id in review_ids}
        if review_ids:
            cursor.execute(
                """
                SELECT
                    review_id,
                    id,
                    rank,
                    ubid,
                    record_id,
                    data_record_id,
                    match_type,
                    matched_field,
                    similarity_score,
                    candidate_status,
                    matched_record,
                    metadata,
                    created_at
                FROM event_decision_candidates
                WHERE review_id = ANY(%s)
                ORDER BY review_id, rank ASC, similarity_score DESC NULLS LAST
                """,
                (review_ids,),
            )
            candidate_columns = [description[0] for description in cursor.description]
            for row in cursor.fetchall():
                candidate = dict(zip(candidate_columns, row))
                candidate["matched_record"] = _json_value(candidate["matched_record"])
                candidate["metadata"] = _json_value(candidate["metadata"]) or {}
                candidate["created_at"] = _iso_datetime(candidate["created_at"])
                candidates_by_review_id.setdefault(candidate["review_id"], []).append(candidate)
    connection.commit()

    for review in reviews:
        review["raw_event"] = _json_value(review["raw_event"])
        review["match_payload"] = _json_value(review["match_payload"]) or {}
        review["match_response"] = _json_value(review["match_response"]) or {}
        review["created_at"] = _iso_datetime(review["created_at"])
        review["resolved_at"] = _iso_datetime(review["resolved_at"])
        review["candidates"] = candidates_by_review_id.get(review["review_id"], [])

    return reviews


def resolve_event_review(review_id: str, request: EventReviewResolutionRequest) -> dict[str, Any]:
    selected_ubid = (request.ubid or "").strip()
    if not selected_ubid:
        raise ValueError("ubid is required")

    connection = _get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    rm.status,
                    rm.incoming_event_id,
                    rm.event_id,
                    rm.raw_event,
                    d.id AS decision_id
                FROM event_review_master rm
                JOIN event_decisions d ON d.review_id = rm.review_id
                WHERE rm.review_id = %s
                ORDER BY d.created_at DESC
                LIMIT 1
                FOR UPDATE OF rm
                """,
                (review_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise LookupError(f"Event review not found: {review_id}")

            status, incoming_event_id, event_id, raw_event, decision_id = row
            if status != "PENDING_REVIEW":
                raise ValueError(f"Event review {review_id} is already resolved with status {status}")

            event = _json_value(raw_event) or {}
            cursor.execute(
                """
                UPDATE event_review_master
                SET status = 'RESOLVED_MAPPED',
                    resolved_ubid = %s,
                    remarks = %s,
                    resolved_at = NOW()
                WHERE review_id = %s
                """,
                (selected_ubid, request.remarks, review_id),
            )
            cursor.execute(
                """
                UPDATE event_decisions
                SET decision_status = 'UBID_MANUALLY_MAPPED',
                    matched_ubid = %s,
                    decision_reason = %s
                WHERE id = %s
                """,
                (
                    selected_ubid,
                    f"Manually mapped from event review. {request.remarks or ''}".strip(),
                    decision_id,
                ),
            )
            cursor.execute(
                """
                UPDATE incoming_events
                SET ubid = %s
                WHERE id = %s
                """,
                (selected_ubid, incoming_event_id),
            )
            cursor.execute(
                """
                UPDATE event_decision_candidates
                SET candidate_status = CASE
                    WHEN ubid = %s THEN 'SELECTED'
                    ELSE 'NOT_SELECTED'
                END
                WHERE review_id = %s
                """,
                (selected_ubid, review_id),
            )
            cursor.execute(
                """
                INSERT INTO event_decision_candidates (
                    decision_id,
                    review_id,
                    rank,
                    ubid,
                    match_type,
                    candidate_status,
                    metadata
                )
                VALUES (%s, %s, 0, %s, 'manual', 'SELECTED', %s::jsonb)
                """,
                (
                    decision_id,
                    review_id,
                    selected_ubid,
                    _json_dumps({"remarks": request.remarks, "mapped_by": "admin"}),
                ),
            )

            category_result = _run_status_inference_flow(
                cursor=cursor,
                incoming_event_id=incoming_event_id,
                decision_id=decision_id,
                event=event,
                ubid=selected_ubid,
                trigger="UBID_MANUALLY_MAPPED",
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return {
        "review_id": review_id,
        "status": "RESOLVED_MAPPED",
        "event_id": event_id,
        "ubid": selected_ubid,
        "event_category_result": category_result,
    }


def fetch_event_category_computations(
    ubid: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    connection = _get_connection()
    params: list[Any] = []
    where_clause = ""

    if ubid:
        where_clause = "WHERE ubid = %s"
        params.append(ubid)

    params.append(limit)
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                ubid,
                event_category_id,
                event_category,
                latest_event_id,
                base_weight,
                final_decay_constant,
                multiplication_decay_constant_factor,
                score,
                last_computed_date,
                created_at,
                updated_at
            FROM event_ubid_events_computation
            {where_clause}
            ORDER BY updated_at DESC, id DESC
            LIMIT %s
            """,
            params,
        )
        columns = [description[0] for description in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    connection.commit()

    for row in rows:
        row["last_computed_date"] = row["last_computed_date"].isoformat() if row["last_computed_date"] else None
        row["created_at"] = _iso_datetime(row["created_at"])
        row["updated_at"] = _iso_datetime(row["updated_at"])

    return rows


def fetch_ubid_statuses(
    ubid: str | None = None,
    active_only: bool = True,
    limit: int = 100,
) -> list[dict[str, Any]]:
    connection = _get_connection()
    params: list[Any] = []
    filters: list[str] = []

    if ubid:
        filters.append("ubid = %s")
        params.append(ubid)

    if active_only:
        filters.append("is_active = TRUE")

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)

    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT
                id,
                ubid,
                computed_positive_score,
                computed_negative_score,
                status,
                is_active,
                latest_event_id,
                event_computation_snapshot,
                created_at,
                updated_at,
                deactivated_at
            FROM ubid_status
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            params,
        )
        columns = [description[0] for description in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    connection.commit()

    for row in rows:
        row["event_computation_snapshot"] = _json_value(row["event_computation_snapshot"]) or []
        row["created_at"] = _iso_datetime(row["created_at"])
        row["updated_at"] = _iso_datetime(row["updated_at"])
        row["deactivated_at"] = _iso_datetime(row["deactivated_at"])

    return rows
