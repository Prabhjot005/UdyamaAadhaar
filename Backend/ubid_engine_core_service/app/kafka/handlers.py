import logging

from app.pipeline import process_department_record


logger = logging.getLogger("ubid-engine-core.handlers")


def handle_valid_department_record(record: dict) -> None:
    logger.info("Received valid department record from Kafka: %s", record)
    result = process_department_record(record)
    normalized_record = result.normalized_record

    logger.info("Normalized business name: %s", normalized_record.get("normalized_name"))
    logger.info("Normalized address: %s", normalized_record.get("normalized_address"))
    logger.info("Normalized landmarks: %s", normalized_record.get("normalized_landmarks"))
    logger.info("Normalized pincode: %s", normalized_record.get("normalized_pincode"))
    logger.info("Normalized PAN: %s", normalized_record.get("normalized_pan"))
    logger.info("Normalized GSTIN: %s", normalized_record.get("normalized_gstin"))
    logger.info("Embedding text: %s", result.embedding_text)
    logger.info("Embedding vector dimension: %s", result.embedding_dimension)
    if result.matches:
        for matched_record in result.matches:
            logger.info(
                "Matched existing record: record_id=%s; data_record_id=%s; match_type=%s; matched_field=%s; similarity_score=%s",
                matched_record.record_id,
                matched_record.data_record_id,
                matched_record.match_type,
                matched_record.matched_field,
                matched_record.similarity_score,
            )
    else:
        logger.info("No existing Milvus match found")
    logger.info(
        "Decision result: status=%s; ubid=%s; review_id=%s; top_similarity_score=%s; top_match_record_id=%s",
        result.decision.status,
        result.decision.ubid,
        result.decision.review_id,
        result.decision.top_similarity_score,
        result.decision.top_match_record_id,
    )
    logger.info("Stored embedding in Milvus with record_id: %s", result.milvus_record_id)
