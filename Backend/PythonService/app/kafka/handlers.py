import logging

from app.embeddings import create_embedding
from app.milvus_store import find_department_record_match, store_department_record_embedding
from app.normalization import (
    normalize_address_with_metadata,
    normalize_gstin,
    normalize_name,
    normalize_pan,
    normalize_pincode,
)


logger = logging.getLogger("ubid-engine-core.handlers")


NORMALIZED_SOURCE_FIELDS = {"name", "address", "pincode", "pan", "panNumber", "gstin"}


def _build_embedding_text(normalized_record: dict) -> str:
    return " | ".join(
        f"{key}: {value}"
        for key, value in normalized_record.items()
        if value not in (None, "", [])
    )


def handle_valid_department_record(record: dict) -> None:
    logger.info("Received valid department record from Kafka: %s", record)
    normalized_name = normalize_name(record.get("name"))
    normalized_address = normalize_address_with_metadata(record.get("address"))
    normalized_pincode = normalize_pincode(record.get("pincode") or record.get("address"))
    normalized_pan = normalize_pan(record.get("panNumber") or record.get("pan"))
    normalized_gstin = normalize_gstin(record.get("gstin"), normalized_pincode.normalized_pincode)
    normalized_record = {
        **{
            key: value
            for key, value in record.items()
            if key not in NORMALIZED_SOURCE_FIELDS
        },
        "normalized_name": normalized_name,
        "normalized_address": normalized_address.normalized_address,
        "normalized_landmarks": normalized_address.landmarks,
        "normalized_pincode": normalized_pincode.normalized_pincode,
        "normalized_pan": normalized_pan.normalized_pan,
        "normalized_gstin": normalized_gstin.normalized_gstin,
        "normalized_gstin_state": normalized_gstin.state_name,
    }
    embedding_text = _build_embedding_text(normalized_record)
    embedding_vector = create_embedding(embedding_text)
    matched_record = find_department_record_match(
        normalized_record=normalized_record,
        embedding_vector=embedding_vector,
    )
    milvus_record_id = store_department_record_embedding(
        original_record=record,
        normalized_record=normalized_record,
        embedding_text=embedding_text,
        embedding_vector=embedding_vector,
    )

    logger.info("Normalized business name: %s", normalized_name)
    logger.info(
        "Normalized address: %s; landmarks: %s",
        normalized_address.normalized_address,
        normalized_address.landmarks,
    )
    logger.info("Normalized pincode: %s", normalized_pincode)
    logger.info("Normalized PAN: %s", normalized_pan)
    logger.info("Normalized GSTIN: %s", normalized_gstin)
    logger.info("Embedding text: %s", embedding_text)
    logger.info("Embedding vector dimension: %s", len(embedding_vector))
    logger.info("Embedding vector: %s", embedding_vector)
    if matched_record:
        logger.info(
            "Matched existing record: record_id=%s; mongo_id=%s; match_type=%s; matched_field=%s; similarity_score=%s",
            matched_record.record_id,
            matched_record.mongo_id,
            matched_record.match_type,
            matched_record.matched_field,
            matched_record.similarity_score,
        )
    else:
        logger.info("No existing Milvus match found")
    logger.info("Stored embedding in Milvus with record_id: %s", milvus_record_id)
