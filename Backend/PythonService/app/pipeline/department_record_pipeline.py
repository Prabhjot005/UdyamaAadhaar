import logging
from dataclasses import dataclass

from app.decision_engine import DecisionResult, decide_business_identity
from app.embeddings import build_embedding_text, create_embedding
from app.normalization import normalize_department_record
from app.similarity_matching import DepartmentRecordMatch, find_department_record_matches
from app.vector_storage import store_department_record_embedding


logger = logging.getLogger("ubid-engine-core.pipeline")


@dataclass(frozen=True)
class DepartmentRecordProcessingResult:
    normalized_record: dict
    embedding_text: str
    embedding_dimension: int
    matches: list[DepartmentRecordMatch]
    decision: DecisionResult
    milvus_record_id: str


def process_department_record(record: dict) -> DepartmentRecordProcessingResult:
    normalized_record = normalize_department_record(record)
    embedding_text = build_embedding_text(normalized_record)
    embedding_vector = create_embedding(embedding_text)
    matches = find_department_record_matches(
        normalized_record=normalized_record,
        embedding_vector=embedding_vector,
    )
    logger.info("Found %s candidate match(es) from similarity matching", len(matches))
    decision = decide_business_identity(
        incoming_record=record,
        normalized_record=normalized_record,
        matches=matches,
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
    )
    logger.info(
        "Stored decision in PostgreSQL: status=%s; ubid=%s; review_id=%s",
        decision.status,
        decision.ubid,
        decision.review_id,
    )
    milvus_metadata = {
        **normalized_record,
        "ubid": decision.ubid,
        "review_id": decision.review_id,
        "decision_status": decision.status,
    }
    milvus_record_id = store_department_record_embedding(
        original_record=record,
        normalized_record=milvus_metadata,
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
    )

    return DepartmentRecordProcessingResult(
        normalized_record=normalized_record,
        embedding_text=embedding_text,
        embedding_dimension=len(embedding_vector),
        matches=matches,
        decision=decision,
        milvus_record_id=milvus_record_id,
    )
