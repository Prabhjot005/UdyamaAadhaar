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
    incoming_record_id: int | None = None
    incoming_embedding_id: int | None = None
    decision_id: int | None = None


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
        # Reference-oriented schema: store each incoming record and embedding once,
        # then point decisions/reviews/match candidates at those IDs.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incoming_department_records (
                id BIGSERIAL PRIMARY KEY,
                mongo_id VARCHAR(128),
                raw_record JSONB NOT NULL,
                normalized_record JSONB NOT NULL,
                normalized_name TEXT,
                normalized_address TEXT,
                normalized_gstin VARCHAR(32),
                normalized_pan VARCHAR(16),
                normalized_pincode VARCHAR(16),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS record_embeddings (
                id BIGSERIAL PRIMARY KEY,
                incoming_record_id BIGINT NOT NULL REFERENCES incoming_department_records(id),
                model_name TEXT NOT NULL,
                embedding_text TEXT NOT NULL,
                embedding_dimension INTEGER NOT NULL,
                embedding_vector JSONB NOT NULL,
                embedding_reasoning JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ubid_master (
                ubid VARCHAR(64) PRIMARY KEY,
                current_record_id BIGINT REFERENCES incoming_department_records(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS review_master (
                review_id VARCHAR(64) PRIMARY KEY,
                incoming_record_id BIGINT NOT NULL REFERENCES incoming_department_records(id),
                suggested_ubid VARCHAR(64),
                status VARCHAR(64) NOT NULL,
                top_similarity_score DOUBLE PRECISION,
                top_match_record_id VARCHAR(128),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS business_identity_decisions (
                id BIGSERIAL PRIMARY KEY,
                incoming_record_id BIGINT NOT NULL REFERENCES incoming_department_records(id),
                embedding_id BIGINT NOT NULL REFERENCES record_embeddings(id),
                decision_status VARCHAR(64) NOT NULL,
                ubid VARCHAR(64),
                review_id VARCHAR(64),
                top_similarity_score DOUBLE PRECISION,
                top_match_record_id VARCHAR(128),
                decision_reason TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_match_candidates (
                id BIGSERIAL PRIMARY KEY,
                decision_id BIGINT NOT NULL REFERENCES business_identity_decisions(id),
                rank INTEGER NOT NULL,
                matched_record_id VARCHAR(128),
                matched_mongo_id VARCHAR(128),
                matched_ubid VARCHAR(64),
                match_type VARCHAR(64) NOT NULL,
                matched_field VARCHAR(64),
                similarity_score DOUBLE PRECISION NOT NULL,
                matched_embedding_text TEXT,
                matched_metadata JSONB,
                match_reason TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_mongo_id ON incoming_department_records (mongo_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_gstin ON incoming_department_records (normalized_gstin)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_pan ON incoming_department_records (normalized_pan)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_pincode ON incoming_department_records (normalized_pincode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_record_embeddings_record_id ON record_embeddings (incoming_record_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_record_id ON business_identity_decisions (incoming_record_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_ubid ON business_identity_decisions (ubid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_candidates_decision_id ON decision_match_candidates (decision_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_master_record_id ON review_master (incoming_record_id)")
    connection.commit()


def initialize_decision_engine_storage() -> None:
    _get_connection()


def _top_match(matches: Iterable[DepartmentRecordMatch]) -> DepartmentRecordMatch | None:
    return max(matches, key=lambda match: match.similarity_score, default=None)


def _matched_ubid(match: DepartmentRecordMatch | None) -> str | None:
    if not match:
        return None

    metadata = match.metadata or {}
    return _record_value(metadata, "ubid") or None


def _lookup_ubid_for_match(cursor, match: DepartmentRecordMatch | None) -> str | None:
    if not match:
        return None

    existing_ubid = _matched_ubid(match)
    if existing_ubid:
        return existing_ubid

    mongo_id = match.mongo_id or ""
    metadata = match.metadata or {}
    gstin = _record_value(metadata, "normalized_gstin")
    pan = _record_value(metadata, "normalized_pan")
    pincode = _record_value(metadata, "normalized_pincode")

    cursor.execute(
        """
        SELECT d.ubid
        FROM business_identity_decisions d
        JOIN incoming_department_records r ON r.id = d.incoming_record_id
        WHERE d.ubid IS NOT NULL
          AND (
                (%s <> '' AND r.mongo_id = %s)
             OR (%s <> '' AND r.normalized_gstin = %s)
             OR (%s <> '' AND r.normalized_pan = %s)
             OR (%s <> '' AND r.normalized_pincode = %s)
          )
        ORDER BY d.created_at DESC
        LIMIT 1
        """,
        (mongo_id, mongo_id, gstin, gstin, pan, pan, pincode, pincode),
    )
    row = cursor.fetchone()
    return row[0] if row else match.record_id


def _insert_incoming_record(cursor, incoming_record: dict, normalized_record: dict) -> int:
    cursor.execute(
        """
        INSERT INTO incoming_department_records (
            mongo_id,
            raw_record,
            normalized_record,
            normalized_name,
            normalized_address,
            normalized_gstin,
            normalized_pan,
            normalized_pincode
        )
        VALUES (%s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            _mongo_id(normalized_record),
            _json_dumps(incoming_record),
            _json_dumps(normalized_record),
            _record_value(normalized_record, "normalized_name"),
            _record_value(normalized_record, "normalized_address"),
            _record_value(normalized_record, "normalized_gstin"),
            _record_value(normalized_record, "normalized_pan"),
            _record_value(normalized_record, "normalized_pincode"),
        ),
    )
    return cursor.fetchone()[0]


def _insert_embedding(
    cursor,
    incoming_record_id: int,
    embedding_text: str,
    embedding_reasoning: dict,
    embedding_vector: list[float],
) -> int:
    cursor.execute(
        """
        INSERT INTO record_embeddings (
            incoming_record_id,
            model_name,
            embedding_text,
            embedding_dimension,
            embedding_vector,
            embedding_reasoning
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
        RETURNING id
        """,
        (
            incoming_record_id,
            embedding_reasoning.get("model", ""),
            embedding_text,
            len(embedding_vector),
            _json_dumps(embedding_vector),
            _json_dumps(embedding_reasoning),
        ),
    )
    return cursor.fetchone()[0]


def _upsert_ubid_master(cursor, ubid: str, incoming_record_id: int) -> None:
    cursor.execute(
        """
        INSERT INTO ubid_master (ubid, current_record_id)
        VALUES (%s, %s)
        ON CONFLICT (ubid) DO UPDATE SET
            current_record_id = EXCLUDED.current_record_id,
            updated_at = NOW()
        """,
        (ubid, incoming_record_id),
    )


def _insert_review_master(
    cursor,
    review_id: str,
    incoming_record_id: int,
    suggested_ubid: str | None,
    top_match: DepartmentRecordMatch | None,
) -> None:
    cursor.execute(
        """
        INSERT INTO review_master (
            review_id,
            incoming_record_id,
            suggested_ubid,
            status,
            top_similarity_score,
            top_match_record_id
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            review_id,
            incoming_record_id,
            suggested_ubid,
            "PENDING_REVIEW",
            top_match.similarity_score if top_match else None,
            top_match.record_id if top_match else None,
        ),
    )


def _decision_reason(status: str, top_match: DepartmentRecordMatch | None) -> str:
    if status == "NEW_BUSINESS":
        return "No candidate exceeded similarity score 0.6, so a new UBID was generated."
    if status == "UBID_MATCHED":
        return "Top candidate exceeded similarity score 0.9 or matched by hard key, so the existing UBID was assigned."
    return "Top candidate was above 0.6 and at or below 0.9, so the record was sent for manual review."


def _match_reason(match: DepartmentRecordMatch) -> str:
    if match.match_type == "hard":
        return f"Matched by scalar hard key '{match.matched_field}' and assigned similarity score 1.0."
    if match.match_type == "none":
        return "No Milvus candidate was returned; placeholder row documents the no-match decision."
    return "Matched by cosine vector similarity over normalized_name, normalized_address, and normalized_pincode embeddings."


def _insert_decision(cursor, incoming_record_id: int, embedding_id: int, status: str, ubid: str | None, review_id: str | None, top_match: DepartmentRecordMatch | None) -> int:
    cursor.execute(
        """
        INSERT INTO business_identity_decisions (
            incoming_record_id,
            embedding_id,
            decision_status,
            ubid,
            review_id,
            top_similarity_score,
            top_match_record_id,
            decision_reason
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            incoming_record_id,
            embedding_id,
            status,
            ubid,
            review_id,
            top_match.similarity_score if top_match else None,
            top_match.record_id if top_match else None,
            _decision_reason(status, top_match),
        ),
    )
    return cursor.fetchone()[0]


def _insert_match_candidates(cursor, decision_id: int, matches: list[DepartmentRecordMatch]) -> None:
    rows = matches or [
        DepartmentRecordMatch(
            record_id="",
            mongo_id="",
            similarity_score=0.0,
            match_type="none",
        )
    ]

    for rank, match in enumerate(rows, start=1):
        cursor.execute(
            """
            INSERT INTO decision_match_candidates (
                decision_id,
                rank,
                matched_record_id,
                matched_mongo_id,
                matched_ubid,
                match_type,
                matched_field,
                similarity_score,
                matched_embedding_text,
                matched_metadata,
                match_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                decision_id,
                rank,
                match.record_id,
                match.mongo_id,
                _matched_ubid(match),
                match.match_type,
                match.matched_field,
                match.similarity_score,
                match.embedding_text,
                _json_dumps(match.metadata or {}),
                _match_reason(match),
            ),
        )


def decide_business_identity(
    incoming_record: dict,
    normalized_record: dict,
    matches: list[DepartmentRecordMatch],
    embedding_text: str,
    embedding_reasoning: dict,
    embedding_vector: list[float],
) -> DecisionResult:
    connection = _get_connection()
    top_match = _top_match(matches)
    top_score = top_match.similarity_score if top_match else None

    try:
        with connection.cursor() as cursor:
            incoming_record_id = _insert_incoming_record(cursor, incoming_record, normalized_record)
            embedding_id = _insert_embedding(
                cursor=cursor,
                incoming_record_id=incoming_record_id,
                embedding_text=embedding_text,
                embedding_reasoning=embedding_reasoning,
                embedding_vector=embedding_vector,
            )

            if not top_match or top_match.similarity_score <= NEW_BUSINESS_THRESHOLD:
                status = "NEW_BUSINESS"
                ubid = _generate_ubid()
                review_id = None
                _upsert_ubid_master(cursor, ubid, incoming_record_id)
            elif top_match.similarity_score > AUTO_MATCH_THRESHOLD:
                status = "UBID_MATCHED"
                ubid = _lookup_ubid_for_match(cursor, top_match)
                review_id = None
                _upsert_ubid_master(cursor, ubid, incoming_record_id)
            else:
                status = "REVIEW_REQUIRED"
                ubid = _lookup_ubid_for_match(cursor, top_match)
                review_id = _generate_review_id()
                _insert_review_master(
                    cursor=cursor,
                    review_id=review_id,
                    incoming_record_id=incoming_record_id,
                    suggested_ubid=ubid,
                    top_match=top_match,
                )

            decision_id = _insert_decision(
                cursor=cursor,
                incoming_record_id=incoming_record_id,
                embedding_id=embedding_id,
                status=status,
                ubid=ubid,
                review_id=review_id,
                top_match=top_match,
            )
            _insert_match_candidates(cursor, decision_id, matches)
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
        incoming_record_id=incoming_record_id,
        incoming_embedding_id=embedding_id,
        decision_id=decision_id,
    )
