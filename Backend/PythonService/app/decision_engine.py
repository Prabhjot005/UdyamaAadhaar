import json
import os
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from app.similarity_matching import DepartmentRecordMatch


NEW_BUSINESS_THRESHOLD = 0.6
AUTO_MATCH_THRESHOLD = 0.9


@dataclass(frozen=True)
class DecisionResult:
    status: str
    ubid: str | None
    review_id: str | None
    top_similarity_score: float | None
    top_match_record_id: str | None


def _postgres_host() -> str:
    return os.getenv("POSTGRES_HOST", "localhost")


def _postgres_port() -> str:
    return os.getenv("POSTGRES_PORT", "5432")


def _postgres_db() -> str:
    return os.getenv("POSTGRES_DB", "postgres")


def _postgres_user() -> str:
    return os.getenv("POSTGRES_USER", "admin")


def _postgres_password() -> str:
    return os.getenv("POSTGRES_PASSWORD", "admin")


def _mongo_id(record: dict) -> str:
    return str(record.get("mongoId") or record.get("mongo_id") or "")


def _record_value(record: dict, key: str) -> str:
    return str(record.get(key) or "")


def _generate_ubid() -> str:
    return f"UBID-{uuid.uuid4().hex[:12].upper()}"


def _generate_review_id() -> str:
    return f"REV-{uuid.uuid4().hex[:12].upper()}"


def _json_dumps(value) -> str:
    return json.dumps(value, default=str)


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
            CREATE TABLE IF NOT EXISTS ubid_master (
                ubid VARCHAR(64) PRIMARY KEY,
                mongo_id VARCHAR(128),
                name TEXT,
                address TEXT,
                gstin VARCHAR(32),
                pan VARCHAR(16),
                pincode VARCHAR(16),
                normalized_record JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS review_master (
                review_id VARCHAR(64) PRIMARY KEY,
                suggested_ubid VARCHAR(64),
                mongo_id VARCHAR(128),
                status VARCHAR(64) NOT NULL,
                top_similarity_score DOUBLE PRECISION,
                top_match_record_id VARCHAR(128),
                incoming_record JSONB NOT NULL,
                normalized_record JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_match_entries (
                id BIGSERIAL PRIMARY KEY,
                decision_status VARCHAR(64) NOT NULL,
                ubid VARCHAR(64),
                review_id VARCHAR(64),
                incoming_mongo_id VARCHAR(128),
                matched_record_id VARCHAR(128),
                matched_mongo_id VARCHAR(128),
                match_type VARCHAR(64),
                matched_field VARCHAR(64),
                similarity_score DOUBLE PRECISION,
                embedding_text TEXT,
                matched_embedding_text TEXT,
                incoming_embedding JSONB NOT NULL,
                embedding_dimension INTEGER NOT NULL,
                incoming_record JSONB NOT NULL,
                normalized_record JSONB NOT NULL,
                matched_metadata JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            "ALTER TABLE decision_match_entries ADD COLUMN IF NOT EXISTS matched_embedding_text TEXT"
        )
        cursor.execute(
            "ALTER TABLE decision_match_entries ADD COLUMN IF NOT EXISTS incoming_embedding JSONB"
        )
        cursor.execute(
            "UPDATE decision_match_entries SET incoming_embedding = '[]'::jsonb WHERE incoming_embedding IS NULL"
        )
        cursor.execute(
            "ALTER TABLE decision_match_entries ALTER COLUMN incoming_embedding SET NOT NULL"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ubid_master_mongo_id ON ubid_master (mongo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ubid_master_gstin ON ubid_master (gstin)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ubid_master_pan ON ubid_master (pan)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ubid_master_pincode ON ubid_master (pincode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_match_entries_ubid ON decision_match_entries (ubid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_match_entries_review_id ON decision_match_entries (review_id)")
    connection.commit()


def initialize_decision_engine_storage() -> None:
    _get_connection()


def _top_match(matches: Iterable[DepartmentRecordMatch]) -> DepartmentRecordMatch | None:
    return max(matches, key=lambda match: match.similarity_score, default=None)


def _lookup_ubid_for_match(cursor, match: DepartmentRecordMatch | None) -> str | None:
    if not match:
        return None

    mongo_id = match.mongo_id or ""
    matched_metadata = match.metadata or {}
    existing_ubid = _record_value(matched_metadata, "ubid")
    if existing_ubid:
        return existing_ubid

    gstin = _record_value(matched_metadata, "normalized_gstin")
    pan = _record_value(matched_metadata, "normalized_pan")
    pincode = _record_value(matched_metadata, "normalized_pincode")

    cursor.execute(
        """
        SELECT ubid
        FROM ubid_master
        WHERE (%s <> '' AND mongo_id = %s)
           OR (%s <> '' AND gstin = %s)
           OR (%s <> '' AND pan = %s)
           OR (%s <> '' AND pincode = %s)
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (mongo_id, mongo_id, gstin, gstin, pan, pan, pincode, pincode),
    )
    row = cursor.fetchone()
    return row[0] if row else match.record_id


def _insert_ubid_master(cursor, ubid: str, normalized_record: dict) -> None:
    cursor.execute(
        """
        INSERT INTO ubid_master (
            ubid,
            mongo_id,
            name,
            address,
            gstin,
            pan,
            pincode,
            normalized_record
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (ubid) DO UPDATE SET
            mongo_id = EXCLUDED.mongo_id,
            name = COALESCE(NULLIF(EXCLUDED.name, ''), ubid_master.name),
            address = COALESCE(NULLIF(EXCLUDED.address, ''), ubid_master.address),
            gstin = COALESCE(NULLIF(EXCLUDED.gstin, ''), ubid_master.gstin),
            pan = COALESCE(NULLIF(EXCLUDED.pan, ''), ubid_master.pan),
            pincode = COALESCE(NULLIF(EXCLUDED.pincode, ''), ubid_master.pincode),
            normalized_record = EXCLUDED.normalized_record,
            updated_at = NOW()
        """,
        (
            ubid,
            _mongo_id(normalized_record),
            _record_value(normalized_record, "normalized_name"),
            _record_value(normalized_record, "normalized_address"),
            _record_value(normalized_record, "normalized_gstin"),
            _record_value(normalized_record, "normalized_pan"),
            _record_value(normalized_record, "normalized_pincode"),
            _json_dumps(normalized_record),
        ),
    )


def _insert_review_master(
    cursor,
    review_id: str,
    suggested_ubid: str | None,
    top_match: DepartmentRecordMatch | None,
    incoming_record: dict,
    normalized_record: dict,
) -> None:
    cursor.execute(
        """
        INSERT INTO review_master (
            review_id,
            suggested_ubid,
            mongo_id,
            status,
            top_similarity_score,
            top_match_record_id,
            incoming_record,
            normalized_record
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        """,
        (
            review_id,
            suggested_ubid,
            _mongo_id(normalized_record),
            "PENDING_REVIEW",
            top_match.similarity_score if top_match else None,
            top_match.record_id if top_match else None,
            _json_dumps(incoming_record),
            _json_dumps(normalized_record),
        ),
    )


def _insert_decision_match_entries(
    cursor,
    matches: list[DepartmentRecordMatch],
    decision_status: str,
    ubid: str | None,
    review_id: str | None,
    incoming_record: dict,
    normalized_record: dict,
    embedding_text: str,
    embedding_vector: list[float],
) -> None:
    rows = matches or [
        DepartmentRecordMatch(
            record_id="",
            mongo_id="",
            similarity_score=0.0,
            match_type="none",
        )
    ]

    for match in rows:
        cursor.execute(
            """
            INSERT INTO decision_match_entries (
                decision_status,
                ubid,
                review_id,
                incoming_mongo_id,
                matched_record_id,
                matched_mongo_id,
                match_type,
                matched_field,
                similarity_score,
                embedding_text,
                matched_embedding_text,
                incoming_embedding,
                embedding_dimension,
                incoming_record,
                normalized_record,
                matched_metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            """,
            (
                decision_status,
                ubid,
                review_id,
                _mongo_id(normalized_record),
                match.record_id,
                match.mongo_id,
                match.match_type,
                match.matched_field,
                match.similarity_score,
                embedding_text,
                match.embedding_text,
                _json_dumps(embedding_vector),
                len(embedding_vector),
                _json_dumps(incoming_record),
                _json_dumps(normalized_record),
                _json_dumps(match.metadata or {}),
            ),
        )


def decide_business_identity(
    incoming_record: dict,
    normalized_record: dict,
    matches: list[DepartmentRecordMatch],
    embedding_text: str,
    embedding_vector: list[float],
) -> DecisionResult:
    connection = _get_connection()
    top_match = _top_match(matches)
    top_score = top_match.similarity_score if top_match else None

    try:
        with connection.cursor() as cursor:
            if not top_match or top_match.similarity_score <= NEW_BUSINESS_THRESHOLD:
                status = "NEW_BUSINESS"
                ubid = _generate_ubid()
                review_id = None
                _insert_ubid_master(cursor, ubid, normalized_record)
            elif top_match.similarity_score > AUTO_MATCH_THRESHOLD:
                status = "UBID_MATCHED"
                ubid = _lookup_ubid_for_match(cursor, top_match)
                review_id = None
                _insert_ubid_master(cursor, ubid, normalized_record)
            else:
                status = "REVIEW_REQUIRED"
                ubid = _lookup_ubid_for_match(cursor, top_match)
                review_id = _generate_review_id()
                _insert_review_master(
                    cursor=cursor,
                    review_id=review_id,
                    suggested_ubid=ubid,
                    top_match=top_match,
                    incoming_record=incoming_record,
                    normalized_record=normalized_record,
                )

            _insert_decision_match_entries(
                cursor=cursor,
                matches=matches,
                decision_status=status,
                ubid=ubid,
                review_id=review_id,
                incoming_record=incoming_record,
                normalized_record=normalized_record,
                embedding_text=embedding_text,
                embedding_vector=embedding_vector,
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return DecisionResult(
        status=status,
        ubid=ubid,
        review_id=review_id,
        top_similarity_score=top_score,
        top_match_record_id=top_match.record_id if top_match else None,
    )
