import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field, model_validator

from app.similarity_matching import DepartmentRecordMatch


NEW_BUSINESS_THRESHOLD = 0.7
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


class ReviewResolutionRequest(BaseModel):
    action: Literal["MATCH_EXISTING", "GENERATE_NEW_UBID"]
    selected_candidate_id: int | None = None
    matched_data_record_id: str | None = None
    remarks: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_selection(self):
        if self.action == "MATCH_EXISTING" and not self.selected_candidate_id and not self.matched_data_record_id:
            raise ValueError("selected_candidate_id or matched_data_record_id is required for MATCH_EXISTING")
        return self


class ReviewResolutionResult(BaseModel):
    review_id: str
    status: str
    ubid: str
    action: str
    selected_candidate_id: int | None = None
    matched_data_record_id: str | None = None
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


def _data_record_id(record: dict) -> str:
    return str(record.get("dataRecordId") or record.get("data_record_id") or record.get("recordId") or record.get("record_id") or record.get("mongoId") or record.get("mongo_id") or "")


def _record_value(record: dict, key: str) -> str:
    return str(record.get(key) or "")


def _generate_ubid() -> str:
    return f"UBID-{uuid.uuid4().hex[:12].upper()}"


def _generate_review_id() -> str:
    return f"REV-{uuid.uuid4().hex[:12].upper()}"


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
                data_record_id VARCHAR(128),
                department_record_id VARCHAR(128),
                source_system VARCHAR(128),
                raw_record JSONB NOT NULL,
                normalized_record JSONB NOT NULL,
                normalized_name TEXT,
                normalized_address TEXT,
                normalized_other_address TEXT,
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
                data_record_id VARCHAR(128),
                normalized_record JSONB NOT NULL DEFAULT '{}'::jsonb,
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
                name TEXT,
                address TEXT,
                gstin VARCHAR(32),
                pan VARCHAR(16),
                pincode VARCHAR(16),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS review_master (
                review_id VARCHAR(64) PRIMARY KEY,
                data_record_id VARCHAR(128),
                incoming_record_id BIGINT NOT NULL REFERENCES incoming_department_records(id),
                suggested_ubid VARCHAR(64),
                status VARCHAR(64) NOT NULL,
                top_similarity_score DOUBLE PRECISION,
                top_match_record_id VARCHAR(128),
                selected_candidate_id BIGINT,
                selected_matched_data_record_id VARCHAR(128),
                resolved_ubid VARCHAR(64),
                remarks TEXT,
                resolved_at TIMESTAMPTZ,
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
                incoming_data_record_id VARCHAR(128),
                matched_data_record_id VARCHAR(128),
                review_id VARCHAR(64),
                candidate_status VARCHAR(64) NOT NULL DEFAULT 'RECORDED',
                rank INTEGER NOT NULL,
                matched_record_id VARCHAR(128),
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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS data_record_ubid_map (
                id BIGSERIAL PRIMARY KEY,
                incoming_record_id BIGINT NOT NULL REFERENCES incoming_department_records(id),
                data_record_id VARCHAR(128),
                matched_record_id VARCHAR(128),
                matched_data_record_id VARCHAR(128),
                ubid VARCHAR(64),
                status VARCHAR(64) NOT NULL,
                reason TEXT NOT NULL,
                review_id VARCHAR(64),
                decision_id BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute("ALTER TABLE incoming_department_records ADD COLUMN IF NOT EXISTS data_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_department_records ADD COLUMN IF NOT EXISTS department_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_department_records ADD COLUMN IF NOT EXISTS source_system VARCHAR(128)")
        cursor.execute("ALTER TABLE incoming_department_records ADD COLUMN IF NOT EXISTS normalized_other_address TEXT")
        cursor.execute("ALTER TABLE record_embeddings ADD COLUMN IF NOT EXISTS data_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE record_embeddings ADD COLUMN IF NOT EXISTS normalized_record JSONB NOT NULL DEFAULT '{}'::jsonb")
        cursor.execute("ALTER TABLE ubid_master ADD COLUMN IF NOT EXISTS name TEXT")
        cursor.execute("ALTER TABLE ubid_master ADD COLUMN IF NOT EXISTS address TEXT")
        cursor.execute("ALTER TABLE ubid_master ADD COLUMN IF NOT EXISTS gstin VARCHAR(32)")
        cursor.execute("ALTER TABLE ubid_master ADD COLUMN IF NOT EXISTS pan VARCHAR(16)")
        cursor.execute("ALTER TABLE ubid_master ADD COLUMN IF NOT EXISTS pincode VARCHAR(16)")
        cursor.execute("ALTER TABLE decision_match_candidates ADD COLUMN IF NOT EXISTS incoming_data_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE decision_match_candidates ADD COLUMN IF NOT EXISTS review_id VARCHAR(64)")
        cursor.execute("ALTER TABLE decision_match_candidates ADD COLUMN IF NOT EXISTS candidate_status VARCHAR(64) NOT NULL DEFAULT 'RECORDED'")
        cursor.execute("ALTER TABLE data_record_ubid_map ADD COLUMN IF NOT EXISTS matched_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE data_record_ubid_map ADD COLUMN IF NOT EXISTS matched_data_record_id VARCHAR(128)")
        cursor.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'incoming_department_records'
                      AND column_name = 'mongo_id'
                ) THEN
                    UPDATE incoming_department_records
                    SET data_record_id = mongo_id
                    WHERE data_record_id IS NULL AND mongo_id IS NOT NULL;
                END IF;
            END $$;
            """
        )
        cursor.execute("ALTER TABLE decision_match_candidates ADD COLUMN IF NOT EXISTS matched_data_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE review_master ADD COLUMN IF NOT EXISTS data_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE review_master ADD COLUMN IF NOT EXISTS selected_candidate_id BIGINT")
        cursor.execute("ALTER TABLE review_master ADD COLUMN IF NOT EXISTS selected_matched_data_record_id VARCHAR(128)")
        cursor.execute("ALTER TABLE review_master ADD COLUMN IF NOT EXISTS resolved_ubid VARCHAR(64)")
        cursor.execute("ALTER TABLE review_master ADD COLUMN IF NOT EXISTS remarks TEXT")
        cursor.execute("ALTER TABLE review_master ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ")
        cursor.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'decision_match_candidates'
                      AND column_name = 'matched_mongo_id'
                ) THEN
                    UPDATE decision_match_candidates
                    SET matched_data_record_id = matched_mongo_id
                    WHERE matched_data_record_id IS NULL AND matched_mongo_id IS NOT NULL;
                END IF;
            END $$;
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_data_record_id ON incoming_department_records (data_record_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_department_source ON incoming_department_records (department_record_id, source_system)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_gstin ON incoming_department_records (normalized_gstin)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_pan ON incoming_department_records (normalized_pan)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_incoming_department_records_pincode ON incoming_department_records (normalized_pincode)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_record_embeddings_record_id ON record_embeddings (incoming_record_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_record_id ON business_identity_decisions (incoming_record_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_ubid ON business_identity_decisions (ubid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_candidates_decision_id ON decision_match_candidates (decision_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_match_candidates_incoming_data_record_id ON decision_match_candidates (incoming_data_record_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_record_ubid_map_data_record_id ON data_record_ubid_map (data_record_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_master_record_id ON review_master (incoming_record_id)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_review_master_data_record_id_unique ON review_master (data_record_id) WHERE data_record_id IS NOT NULL AND data_record_id <> ''")
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

    data_record_id = match.data_record_id or ""
    metadata = match.metadata or {}
    gstin = _record_value(metadata, "normalized_gstin")
    pan = _record_value(metadata, "normalized_pan")
    cursor.execute(
        """
        SELECT d.ubid
        FROM business_identity_decisions d
        JOIN incoming_department_records r ON r.id = d.incoming_record_id
        WHERE d.ubid IS NOT NULL
          AND (
                (%s <> '' AND r.data_record_id = %s)
             OR (%s <> '' AND r.normalized_gstin = %s)
             OR (%s <> '' AND r.normalized_pan = %s)
          )
        ORDER BY d.created_at DESC
        LIMIT 1
        """,
        (data_record_id, data_record_id, gstin, gstin, pan, pan),
    )
    row = cursor.fetchone()
    return row[0] if row else match.record_id


def enrich_department_record_matches(matches: list[DepartmentRecordMatch]) -> list[dict[str, Any]]:
    connection = _get_connection()
    enriched_matches: list[dict[str, Any]] = []

    with connection.cursor() as cursor:
        for match in matches:
            ubid = _lookup_ubid_for_match(cursor, match)
            matched_record = None

            if match.data_record_id:
                cursor.execute(
                    """
                    SELECT
                        id,
                        raw_record,
                        normalized_record,
                        normalized_name,
                        normalized_address,
                        normalized_other_address,
                        normalized_gstin,
                        normalized_pan,
                        normalized_pincode,
                        source_system,
                        created_at
                    FROM incoming_department_records
                    WHERE data_record_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (match.data_record_id,),
                )
                row = cursor.fetchone()
                if row:
                    matched_record = {
                        "incoming_record_id": row[0],
                        "raw_record": _json_value(row[1]),
                        "normalized_record": _json_value(row[2]),
                        "normalized_name": row[3],
                        "normalized_address": row[4],
                        "normalized_other_address": row[5],
                        "normalized_gstin": row[6],
                        "normalized_pan": row[7],
                        "normalized_pincode": row[8],
                        "source_system": row[9],
                        "created_at": _iso_datetime(row[10]),
                    }

            enriched_matches.append(
                {
                    "ubid": ubid,
                    "record_id": match.record_id,
                    "data_record_id": match.data_record_id,
                    "similarity_score": match.similarity_score,
                    "match_type": match.match_type,
                    "matched_field": match.matched_field,
                    "embedding_text": match.embedding_text,
                    "metadata": match.metadata or {},
                    "matched_record": matched_record,
                }
            )

    connection.commit()
    return enriched_matches


def _insert_incoming_record(cursor, incoming_record: dict, normalized_record: dict) -> int:
    cursor.execute(
        """
        INSERT INTO incoming_department_records (
            data_record_id,
            department_record_id,
            source_system,
            raw_record,
            normalized_record,
            normalized_name,
            normalized_address,
            normalized_other_address,
            normalized_gstin,
            normalized_pan,
            normalized_pincode
        )
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            _data_record_id(normalized_record),
            _record_value(normalized_record, "departmentRecordId") or _record_value(normalized_record, "department_record_id") or _record_value(normalized_record, "deptRecordId") or _record_value(normalized_record, "dept_record_id"),
            _record_value(normalized_record, "sourceSystem") or _record_value(normalized_record, "source_system") or _record_value(normalized_record, "source"),
            _json_dumps(incoming_record),
            _json_dumps(normalized_record),
            _record_value(normalized_record, "normalized_name"),
            _record_value(normalized_record, "normalized_address"),
            _record_value(normalized_record, "normalized_other_address"),
            _record_value(normalized_record, "normalized_gstin"),
            _record_value(normalized_record, "normalized_pan"),
            _record_value(normalized_record, "normalized_pincode"),
        ),
    )
    return cursor.fetchone()[0]


def _insert_embedding(
    cursor,
    incoming_record_id: int,
    data_record_id: str,
    normalized_record: dict,
    embedding_text: str,
    embedding_reasoning: dict,
    embedding_vector: list[float],
) -> int:
    cursor.execute(
        """
        INSERT INTO record_embeddings (
            incoming_record_id,
            data_record_id,
            normalized_record,
            model_name,
            embedding_text,
            embedding_dimension,
            embedding_vector,
            embedding_reasoning
        )
        VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb)
        RETURNING id
        """,
        (
            incoming_record_id,
            data_record_id,
            _json_dumps(normalized_record),
            embedding_reasoning.get("model", ""),
            embedding_text,
            len(embedding_vector),
            _json_dumps(embedding_vector),
            _json_dumps(embedding_reasoning),
        ),
    )
    return cursor.fetchone()[0]


def _upsert_ubid_master(cursor, ubid: str, incoming_record_id: int, normalized_record: dict) -> None:
    cursor.execute(
        """
        INSERT INTO ubid_master (ubid, current_record_id, name, address, gstin, pan, pincode)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ubid) DO UPDATE SET
            current_record_id = EXCLUDED.current_record_id,
            name = COALESCE(NULLIF(TRIM(EXCLUDED.name), ''), ubid_master.name),
            address = COALESCE(NULLIF(TRIM(EXCLUDED.address), ''), ubid_master.address),
            gstin = COALESCE(NULLIF(TRIM(EXCLUDED.gstin), ''), ubid_master.gstin),
            pan = COALESCE(NULLIF(TRIM(EXCLUDED.pan), ''), ubid_master.pan),
            pincode = COALESCE(NULLIF(TRIM(EXCLUDED.pincode), ''), ubid_master.pincode),
            updated_at = NOW()
        """,
        (
            ubid,
            incoming_record_id,
            _record_value(normalized_record, "normalized_name") or None,
            _record_value(normalized_record, "normalized_address") or _record_value(normalized_record, "normalized_other_address") or None,
            _record_value(normalized_record, "normalized_gstin") or None,
            _record_value(normalized_record, "normalized_pan") or None,
            _record_value(normalized_record, "normalized_pincode") or None,
        ),
    )


def _find_ubid_for_data_record_id(cursor, data_record_id: str | None) -> str | None:
    if not data_record_id:
        return None

    cursor.execute(
        """
        SELECT m.ubid
        FROM data_record_ubid_map m
        WHERE m.data_record_id = %s
          AND m.ubid IS NOT NULL
          AND m.status IN ('ASSIGNED', 'CONFIRMED')
        ORDER BY m.updated_at DESC, m.created_at DESC
        LIMIT 1
        """,
        (data_record_id,),
    )
    row = cursor.fetchone()
    if row:
        return row[0]

    cursor.execute(
        """
        SELECT d.ubid
        FROM business_identity_decisions d
        JOIN incoming_department_records r ON r.id = d.incoming_record_id
        WHERE r.data_record_id = %s
          AND d.ubid IS NOT NULL
        ORDER BY d.created_at DESC
        LIMIT 1
        """,
        (data_record_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _insert_review_master(
    cursor,
    review_id: str,
    data_record_id: str,
    incoming_record_id: int,
    suggested_ubid: str | None,
    top_match: DepartmentRecordMatch | None,
) -> str:
    cursor.execute(
        """
        INSERT INTO review_master (
            review_id,
            data_record_id,
            incoming_record_id,
            suggested_ubid,
            status,
            top_similarity_score,
            top_match_record_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (data_record_id) WHERE data_record_id IS NOT NULL AND data_record_id <> ''
        DO UPDATE SET
            incoming_record_id = EXCLUDED.incoming_record_id,
            suggested_ubid = EXCLUDED.suggested_ubid,
            top_similarity_score = EXCLUDED.top_similarity_score,
            top_match_record_id = EXCLUDED.top_match_record_id
        RETURNING review_id
        """,
        (
            review_id,
            data_record_id,
            incoming_record_id,
            suggested_ubid,
            "PENDING_REVIEW",
            top_match.similarity_score if top_match else None,
            top_match.record_id if top_match else None,
        ),
    )
    return cursor.fetchone()[0]


def _decision_reason(status: str, top_match: DepartmentRecordMatch | None) -> str:
    if status == "NEW_BUSINESS":
        return "All candidates were below similarity score 0.7, so a new UBID was generated."
    if status == "UBID_MATCHED":
        return "Top candidate exceeded similarity score 0.9 or matched by hard key, so the existing UBID was assigned."
    return "Top candidate was between 0.7 and 0.9, so the record was sent for manual review."


def _match_reason(match: DepartmentRecordMatch) -> str:
    if match.match_type == "hard":
        return f"Matched by scalar hard key '{match.matched_field}' and assigned similarity score 1.0."
    if match.match_type == "none":
        return "No Milvus candidate was returned; placeholder row documents the no-match decision."
    return "Matched by weighted vector similarity using name 65%, pincode 25%, and address 10% after Milvus candidate retrieval."


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


def _insert_match_candidates(
    cursor,
    decision_id: int,
    incoming_data_record_id: str,
    review_id: str | None,
    candidate_status: str,
    matches: list[DepartmentRecordMatch],
) -> None:
    for rank, match in enumerate(matches, start=1):
        cursor.execute(
            """
            INSERT INTO decision_match_candidates (
                decision_id,
                incoming_data_record_id,
                matched_data_record_id,
                review_id,
                candidate_status,
                rank,
                matched_record_id,
                matched_ubid,
                match_type,
                matched_field,
                similarity_score,
                matched_embedding_text,
                matched_metadata,
                match_reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                decision_id,
                incoming_data_record_id,
                match.data_record_id,
                review_id,
                candidate_status,
                rank,
                match.record_id,
                _matched_ubid(match),
                match.match_type,
                match.matched_field,
                match.similarity_score,
                match.embedding_text,
                _json_dumps(match.metadata or {}),
                _match_reason(match),
            ),
        )


def _candidate_matches_for_status(status: str, matches: list[DepartmentRecordMatch], top_match: DepartmentRecordMatch | None) -> list[DepartmentRecordMatch]:
    if status == "UBID_MATCHED":
        return [top_match] if top_match else []
    if status == "REVIEW_REQUIRED":
        review_matches = [
            match
            for match in sorted(matches, key=lambda item: item.similarity_score, reverse=True)
            if NEW_BUSINESS_THRESHOLD <= match.similarity_score <= AUTO_MATCH_THRESHOLD
        ]
        return review_matches[:5]
    return []


def _insert_data_record_ubid_map(
    cursor,
    incoming_record_id: int,
    data_record_id: str,
    top_match: DepartmentRecordMatch | None,
    ubid: str | None,
    status: str,
    reason: str,
    review_id: str | None,
    decision_id: int,
) -> None:
    cursor.execute(
        """
        INSERT INTO data_record_ubid_map (
            incoming_record_id,
            data_record_id,
            matched_record_id,
            matched_data_record_id,
            ubid,
            status,
            reason,
            review_id,
            decision_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            incoming_record_id,
            data_record_id,
            top_match.record_id if top_match else None,
            top_match.data_record_id if top_match else None,
            ubid,
            status,
            reason,
            review_id,
            decision_id,
        ),
    )


def _ubid_map_values(status: str, ubid: str | None) -> tuple[str | None, str, str]:
    if status == "REVIEW_REQUIRED":
        return None, "PENDING", "NO_UBID_ASSIGNED_PENDING_REVIEW"
    if status == "NEW_BUSINESS":
        return ubid, "ASSIGNED", "NEW_UBID_GENERATED"
    return ubid, "ASSIGNED", "MATCH_CONFIRMED"


def _score_value(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100 if value > 1 else value


def _confidence_score_range(confidence: str | None) -> tuple[float | None, float | None]:
    if not confidence or confidence == "All":
        return None, None

    normalized = confidence.strip().lower().replace("%", "")
    if normalized in {"90+", ">=90", "gte90", "high"}:
        return 0.9, None
    if normalized in {"80-90", "80_to_90", "medium-high"}:
        return 0.8, 0.9
    if normalized in {"70-80", "70_to_80", "medium"}:
        return 0.7, 0.8
    if normalized in {"<70", "lt70", "low"}:
        return None, 0.7

    return None, None


def fetch_reviews(
    status: str | None = None,
    search: str | None = None,
    match_confidence: str | None = None,
    min_match_score: float | None = None,
    max_match_score: float | None = None,
) -> list[dict[str, Any]]:
    connection = _get_connection()
    with connection.cursor() as cursor:
        params: list[Any] = []
        filters: list[str] = []
        if status and status != "All":
            filters.append("rm.status = %s")
            params.append(status)

        confidence_min, confidence_max = _confidence_score_range(match_confidence)
        min_score = _score_value(min_match_score) if min_match_score is not None else confidence_min
        max_score = _score_value(max_match_score) if max_match_score is not None else confidence_max

        if min_score is not None:
            filters.append("rm.top_similarity_score >= %s")
            params.append(min_score)
        if max_score is not None:
            filters.append("rm.top_similarity_score < %s")
            params.append(max_score)

        if search and search.strip():
            filters.append(
                """
                LOWER(
                    COALESCE(rm.review_id, '') || ' ' ||
                    COALESCE(rm.data_record_id, '') || ' ' ||
                    COALESCE(rm.suggested_ubid, '') || ' ' ||
                    COALESCE(rm.resolved_ubid, '') || ' ' ||
                    COALESCE(r.normalized_name, '') || ' ' ||
                    COALESCE(r.normalized_address, '') || ' ' ||
                    COALESCE(r.normalized_other_address, '') || ' ' ||
                    COALESCE(r.normalized_gstin, '') || ' ' ||
                    COALESCE(r.normalized_pan, '') || ' ' ||
                    COALESCE(r.normalized_pincode, '') || ' ' ||
                    COALESCE(r.raw_record::text, '') || ' ' ||
                    COALESCE(r.normalized_record::text, '')
                ) LIKE %s
                """
            )
            params.append(f"%{search.strip().lower()}%")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        cursor.execute(
            f"""
            SELECT
                rm.review_id,
                rm.data_record_id,
                rm.status,
                rm.suggested_ubid,
                rm.top_similarity_score,
                rm.top_match_record_id,
                rm.selected_candidate_id,
                rm.selected_matched_data_record_id,
                rm.resolved_ubid,
                rm.remarks,
                rm.resolved_at,
                rm.created_at,
                r.id AS incoming_record_id,
                r.raw_record,
                r.normalized_record,
                r.normalized_name,
                r.normalized_address,
                r.normalized_other_address,
                r.normalized_gstin,
                r.normalized_pan,
                r.normalized_pincode
            FROM review_master rm
            JOIN incoming_department_records r ON r.id = rm.incoming_record_id
            {where_clause}
            ORDER BY rm.created_at DESC
            """,
            params,
        )
        review_columns = [description[0] for description in cursor.description]
        review_rows = cursor.fetchall()
        if not review_rows:
            connection.commit()
            return []

        reviews_by_id: dict[str, dict[str, Any]] = {}
        review_ids: list[str] = []
        for row in review_rows:
            item = dict(zip(review_columns, row))
            review_id = item["review_id"]
            review_ids.append(review_id)
            reviews_by_id[review_id] = {
                "review_id": review_id,
                "data_record_id": item["data_record_id"],
                "status": item["status"],
                "suggested_ubid": item["suggested_ubid"],
                "top_similarity_score": item["top_similarity_score"],
                "top_match_record_id": item["top_match_record_id"],
                "selected_candidate_id": item["selected_candidate_id"],
                "selected_matched_data_record_id": item["selected_matched_data_record_id"],
                "resolved_ubid": item["resolved_ubid"],
                "remarks": item["remarks"],
                "resolved_at": _iso_datetime(item["resolved_at"]),
                "created_at": _iso_datetime(item["created_at"]),
                "incoming_record": {
                    "id": item["incoming_record_id"],
                    "raw_record": _json_value(item["raw_record"]),
                    "normalized_record": _json_value(item["normalized_record"]),
                    "normalized_name": item["normalized_name"],
                    "normalized_address": item["normalized_address"],
                    "normalized_other_address": item["normalized_other_address"],
                    "normalized_gstin": item["normalized_gstin"],
                    "normalized_pan": item["normalized_pan"],
                    "normalized_pincode": item["normalized_pincode"],
                },
                "candidates": [],
            }

        cursor.execute(
            """
            SELECT
                dmc.id,
                dmc.review_id,
                dmc.decision_id,
                dmc.incoming_data_record_id,
                dmc.matched_data_record_id,
                dmc.candidate_status,
                dmc.rank,
                dmc.matched_record_id,
                dmc.matched_ubid,
                dmc.match_type,
                dmc.matched_field,
                dmc.similarity_score,
                dmc.matched_embedding_text,
                dmc.matched_metadata,
                dmc.match_reason,
                dmc.created_at,
                matched.id AS matched_incoming_record_id,
                matched.raw_record AS matched_raw_record,
                matched.normalized_record AS matched_normalized_record,
                matched.normalized_name AS matched_normalized_name,
                matched.normalized_address AS matched_normalized_address,
                matched.normalized_other_address AS matched_normalized_other_address,
                matched.normalized_gstin AS matched_normalized_gstin,
                matched.normalized_pan AS matched_normalized_pan,
                matched.normalized_pincode AS matched_normalized_pincode
            FROM decision_match_candidates dmc
            LEFT JOIN LATERAL (
                SELECT
                    r.id,
                    r.raw_record,
                    r.normalized_record,
                    r.normalized_name,
                    r.normalized_address,
                    r.normalized_other_address,
                    r.normalized_gstin,
                    r.normalized_pan,
                    r.normalized_pincode
                FROM incoming_department_records r
                WHERE r.data_record_id = dmc.matched_data_record_id
                ORDER BY r.created_at DESC
                LIMIT 1
            ) matched ON TRUE
            WHERE dmc.review_id = ANY(%s)
            ORDER BY dmc.review_id, dmc.rank ASC, dmc.similarity_score DESC
            """,
            (review_ids,),
        )
        candidate_columns = [description[0] for description in cursor.description]
        for row in cursor.fetchall():
            candidate = dict(zip(candidate_columns, row))
            review_id = candidate.pop("review_id")
            candidate["matched_metadata"] = _json_value(candidate["matched_metadata"])
            candidate["created_at"] = _iso_datetime(candidate["created_at"])
            candidate["matched_record_data"] = {
                "id": candidate.pop("matched_incoming_record_id"),
                "raw_record": _json_value(candidate.pop("matched_raw_record")),
                "normalized_record": _json_value(candidate.pop("matched_normalized_record")),
                "normalized_name": candidate.pop("matched_normalized_name"),
                "normalized_address": candidate.pop("matched_normalized_address"),
                "normalized_other_address": candidate.pop("matched_normalized_other_address"),
                "normalized_gstin": candidate.pop("matched_normalized_gstin"),
                "normalized_pan": candidate.pop("matched_normalized_pan"),
                "normalized_pincode": candidate.pop("matched_normalized_pincode"),
            }
            reviews_by_id[review_id]["candidates"].append(candidate)

    connection.commit()
    return list(reviews_by_id.values())


def fetch_ubid_master(
    search: str | None = None,
    status: str | None = None,
    source_system: str | None = None,
) -> dict[str, Any]:
    connection = _get_connection()
    with connection.cursor() as cursor:
        params: list[Any] = []
        filters: list[str] = []

        if search and search.strip():
            filters.append(
                """
                LOWER(
                    COALESCE(u.ubid, '') || ' ' ||
                    COALESCE(u.name, '') || ' ' ||
                    COALESCE(u.pan, '') || ' ' ||
                    COALESCE(u.gstin, '') || ' ' ||
                    COALESCE(u.pincode, '') || ' ' ||
                    COALESCE(current_record.raw_record::text, '') || ' ' ||
                    COALESCE(current_record.normalized_record::text, '')
                ) LIKE %s
                """
            )
            params.append(f"%{search.strip().lower()}%")

        if status and status != "All":
            filters.append(
                """
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM review_master rm
                        WHERE rm.suggested_ubid = u.ubid
                          AND rm.status = 'PENDING_REVIEW'
                    ) THEN 'UNDER_REVIEW'
                    ELSE 'ACTIVE'
                END = %s
                """
            )
            params.append(status)

        if source_system and source_system != "All":
            filters.append(
                """
                EXISTS (
                    SELECT 1
                    FROM data_record_ubid_map m
                    JOIN incoming_department_records r ON r.id = m.incoming_record_id
                    WHERE m.ubid = u.ubid
                      AND (
                            r.source_system = %s
                         OR r.raw_record->>'sourceSystem' = %s
                         OR r.raw_record->>'source_system' = %s
                         OR r.raw_record->>'source' = %s
                      )
                )
                """
            )
            params.extend([source_system, source_system, source_system, source_system])

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        cursor.execute(
            f"""
            SELECT
                u.ubid,
                u.name,
                u.address,
                u.gstin,
                u.pan,
                u.pincode,
                u.current_record_id,
                u.created_at,
                u.updated_at,
                current_record.raw_record,
                current_record.normalized_record,
                current_record.normalized_name,
                current_record.normalized_address,
                current_record.normalized_gstin,
                current_record.normalized_pan,
                current_record.normalized_pincode,
                COALESCE(map_stats.constituent_count, 0) AS constituent_count,
                COALESCE(map_stats.source_systems, ARRAY[]::TEXT[]) AS source_systems,
                COALESCE(decision_stats.average_match_confidence, 0) AS average_match_confidence,
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM review_master rm
                        WHERE rm.suggested_ubid = u.ubid
                          AND rm.status = 'PENDING_REVIEW'
                    ) THEN 'UNDER_REVIEW'
                    ELSE 'ACTIVE'
                END AS status
            FROM ubid_master u
            LEFT JOIN incoming_department_records current_record ON current_record.id = u.current_record_id
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(DISTINCT m.data_record_id) AS constituent_count,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT COALESCE(
                        NULLIF(r.source_system, ''),
                        NULLIF(r.raw_record->>'sourceSystem', ''),
                        NULLIF(r.raw_record->>'source_system', ''),
                        NULLIF(r.raw_record->>'source', '')
                    )), NULL) AS source_systems
                FROM data_record_ubid_map m
                LEFT JOIN incoming_department_records r ON r.id = m.incoming_record_id
                WHERE m.ubid = u.ubid
            ) map_stats ON TRUE
            LEFT JOIN LATERAL (
                SELECT AVG(d.top_similarity_score) AS average_match_confidence
                FROM business_identity_decisions d
                WHERE d.ubid = u.ubid
                  AND d.top_similarity_score IS NOT NULL
            ) decision_stats ON TRUE
            {where_clause}
            ORDER BY u.updated_at DESC, u.created_at DESC
            """,
            params,
        )
        columns = [description[0] for description in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    connection.commit()
    ubids: list[dict[str, Any]] = []
    for row in rows:
        raw_record = _json_value(row["raw_record"]) or {}
        normalized_record = _json_value(row["normalized_record"]) or {}
        primary_name = row["name"] or raw_record.get("name") or normalized_record.get("normalized_name") or row["normalized_name"]
        primary_pan = row["pan"] or raw_record.get("pan") or raw_record.get("panNumber") or row["normalized_pan"]
        primary_gstin = row["gstin"] or raw_record.get("gstin") or row["normalized_gstin"]

        ubids.append(
            {
                "ubid": row["ubid"],
                "entity_name": primary_name,
                "address": row["address"] or raw_record.get("address") or row["normalized_address"],
                "primary_pan": primary_pan,
                "primary_gstin": primary_gstin,
                "pincode": row["pincode"] or raw_record.get("pincode") or row["normalized_pincode"],
                "status": row["status"],
                "constituent_count": row["constituent_count"],
                "source_systems": row["source_systems"] or [],
                "average_match_confidence": row["average_match_confidence"],
                "current_record_id": row["current_record_id"],
                "current_record": {
                    "raw_record": raw_record,
                    "normalized_record": normalized_record,
                },
                "created_at": _iso_datetime(row["created_at"]),
                "updated_at": _iso_datetime(row["updated_at"]),
            }
        )

    stats = {
        "total_ubids": len(ubids),
        "active_ubids": sum(1 for item in ubids if item["status"] == "ACTIVE"),
        "inactive_ubids": 0,
        "under_review": sum(1 for item in ubids if item["status"] == "UNDER_REVIEW"),
        "created_today": sum(1 for item in ubids if item["created_at"] and item["created_at"][:10] == datetime.utcnow().date().isoformat()),
    }
    return {"ubids": ubids, "stats": stats}


def resolve_review(review_id: str, request: ReviewResolutionRequest) -> ReviewResolutionResult:
    connection = _get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    rm.status,
                    rm.data_record_id,
                    rm.incoming_record_id,
                    r.normalized_record
                FROM review_master rm
                JOIN incoming_department_records r ON r.id = rm.incoming_record_id
                WHERE rm.review_id = %s
                FOR UPDATE
                """,
                (review_id,),
            )
            review = cursor.fetchone()
            if not review:
                raise LookupError(f"Review not found: {review_id}")

            current_status, incoming_data_record_id, incoming_record_id, normalized_record = review
            if current_status != "PENDING_REVIEW":
                raise ValueError(f"Review {review_id} is already resolved with status {current_status}")

            selected_candidate_id = request.selected_candidate_id
            matched_data_record_id = request.matched_data_record_id
            matched_record_id = None

            if request.action == "GENERATE_NEW_UBID":
                selected_candidate_id = None
                matched_data_record_id = None
                ubid = _generate_ubid()
                resolved_status = "RESOLVED_NEW_UBID"
                decision_status = "NEW_BUSINESS"
                map_reason = "ADMIN_REVIEW_NEW_UBID_GENERATED"
            else:
                candidate_params: list[Any] = [review_id]
                if selected_candidate_id:
                    candidate_filter = "AND id = %s"
                    candidate_params.append(selected_candidate_id)
                else:
                    candidate_filter = "AND matched_data_record_id = %s"
                    candidate_params.append(matched_data_record_id)

                cursor.execute(
                    f"""
                    SELECT id, matched_record_id, matched_data_record_id, matched_ubid
                    FROM decision_match_candidates
                    WHERE review_id = %s
                    {candidate_filter}
                    ORDER BY rank ASC
                    LIMIT 1
                    """,
                    candidate_params,
                )
                candidate = cursor.fetchone()
                if not candidate:
                    raise LookupError(f"Selected candidate was not found for review {review_id}")

                selected_candidate_id, matched_record_id, matched_data_record_id, matched_ubid = candidate
                ubid = matched_ubid or _find_ubid_for_data_record_id(cursor, matched_data_record_id) or matched_record_id
                if not ubid:
                    raise ValueError("Selected candidate does not have enough information to resolve a UBID")
                resolved_status = "RESOLVED_MATCHED"
                decision_status = "UBID_MATCHED"
                map_reason = "ADMIN_REVIEW_MATCH_CONFIRMED"

            _upsert_ubid_master(cursor, ubid, incoming_record_id, _json_value(normalized_record) or {})

            cursor.execute(
                """
                UPDATE review_master
                SET status = %s,
                    selected_candidate_id = %s,
                    selected_matched_data_record_id = %s,
                    resolved_ubid = %s,
                    remarks = %s,
                    resolved_at = NOW()
                WHERE review_id = %s
                """,
                (
                    resolved_status,
                    selected_candidate_id,
                    matched_data_record_id,
                    ubid,
                    request.remarks,
                    review_id,
                ),
            )
            cursor.execute(
                """
                UPDATE business_identity_decisions
                SET decision_status = %s,
                    ubid = %s,
                    top_match_record_id = COALESCE(%s, top_match_record_id),
                    decision_reason = %s
                WHERE review_id = %s
                """,
                (
                    decision_status,
                    ubid,
                    matched_record_id,
                    f"Resolved by admin review. {request.remarks or ''}".strip(),
                    review_id,
                ),
            )
            cursor.execute(
                """
                UPDATE decision_match_candidates
                SET candidate_status = CASE
                    WHEN %s IS NOT NULL AND id = %s THEN 'SELECTED'
                    WHEN %s IS NULL AND %s IS NOT NULL AND matched_data_record_id = %s THEN 'SELECTED'
                    ELSE 'REJECTED'
                END
                WHERE review_id = %s
                """,
                (
                    selected_candidate_id,
                    selected_candidate_id,
                    selected_candidate_id,
                    matched_data_record_id,
                    matched_data_record_id,
                    review_id,
                ),
            )
            cursor.execute(
                """
                UPDATE data_record_ubid_map
                SET ubid = %s,
                    matched_record_id = %s,
                    matched_data_record_id = %s,
                    status = 'ASSIGNED',
                    reason = %s,
                    updated_at = NOW()
                WHERE review_id = %s
                """,
                (ubid, matched_record_id, matched_data_record_id, map_reason, review_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    INSERT INTO data_record_ubid_map (
                        incoming_record_id,
                        data_record_id,
                        matched_record_id,
                        matched_data_record_id,
                        ubid,
                        status,
                        reason,
                        review_id
                    )
                    VALUES (%s, %s, %s, %s, %s, 'ASSIGNED', %s, %s)
                    """,
                    (
                        incoming_record_id,
                        incoming_data_record_id,
                        matched_record_id,
                        matched_data_record_id,
                        ubid,
                        map_reason,
                        review_id,
                    ),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise

    return ReviewResolutionResult(
        review_id=review_id,
        status=resolved_status,
        ubid=ubid,
        action=request.action,
        selected_candidate_id=selected_candidate_id,
        matched_data_record_id=matched_data_record_id,
        remarks=request.remarks,
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
    incoming_data_record_id = _data_record_id(normalized_record)

    try:
        with connection.cursor() as cursor:
            incoming_record_id = _insert_incoming_record(cursor, incoming_record, normalized_record)
            embedding_id = _insert_embedding(
                cursor=cursor,
                incoming_record_id=incoming_record_id,
                data_record_id=incoming_data_record_id,
                normalized_record=normalized_record,
                embedding_text=embedding_text,
                embedding_reasoning=embedding_reasoning,
                embedding_vector=embedding_vector,
            )

            if not top_match or top_match.similarity_score < NEW_BUSINESS_THRESHOLD:
                status = "NEW_BUSINESS"
                ubid = _generate_ubid()
                review_id = None
                _upsert_ubid_master(cursor, ubid, incoming_record_id, normalized_record)
            elif top_match.similarity_score > AUTO_MATCH_THRESHOLD:
                status = "UBID_MATCHED"
                ubid = _lookup_ubid_for_match(cursor, top_match)
                review_id = None
                _upsert_ubid_master(cursor, ubid, incoming_record_id, normalized_record)
            else:
                status = "REVIEW_REQUIRED"
                ubid = _lookup_ubid_for_match(cursor, top_match)
                review_id = _generate_review_id()
                review_id = _insert_review_master(
                    cursor=cursor,
                    review_id=review_id,
                    data_record_id=incoming_data_record_id,
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
            candidate_status = "PENDING_REVIEW" if status == "REVIEW_REQUIRED" else status
            candidate_matches = _candidate_matches_for_status(status, matches, top_match)
            _insert_match_candidates(
                cursor,
                decision_id=decision_id,
                incoming_data_record_id=incoming_data_record_id,
                review_id=review_id,
                candidate_status=candidate_status,
                matches=candidate_matches,
            )
            mapped_ubid, map_status, map_reason = _ubid_map_values(status, ubid)
            _insert_data_record_ubid_map(
                cursor=cursor,
                incoming_record_id=incoming_record_id,
                data_record_id=incoming_data_record_id,
                top_match=top_match,
                ubid=mapped_ubid,
                status=map_status,
                reason=map_reason,
                review_id=review_id,
                decision_id=decision_id,
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
        incoming_record_id=incoming_record_id,
        incoming_embedding_id=embedding_id,
        decision_id=decision_id,
    )
