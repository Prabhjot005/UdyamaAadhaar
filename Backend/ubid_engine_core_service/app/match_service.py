from typing import Any

from pydantic import BaseModel, Field

from app.decision_engine import AUTO_MATCH_THRESHOLD, NEW_BUSINESS_THRESHOLD, enrich_department_record_matches
from app.embeddings import build_embedding_reasoning, build_embedding_text, create_embedding
from app.normalization import normalize_department_record
from app.similarity_matching import find_department_record_matches


class UbidMatchRequest(BaseModel):
    gstin: str | None = None
    pan: str | None = None
    panNumber: str | None = None
    departmentRecordId: str | None = None
    sourceType: str | None = None
    sourceName: str | None = None
    name: str | None = None
    address: str | None = None
    pincode: str | None = None
    limit: int = Field(default=5, ge=1, le=25)


def _request_to_record(request: UbidMatchRequest) -> dict[str, Any]:
    record = request.model_dump(exclude_none=True)

    source = request.sourceType or request.sourceName
    if source:
        record["sourceSystem"] = source

    if request.pan and not request.panNumber:
        record["panNumber"] = request.pan

    return record


def match_ubid(request: UbidMatchRequest) -> dict[str, Any]:
    incoming_record = _request_to_record(request)
    normalized_record = normalize_department_record(incoming_record)
    embedding_text = build_embedding_text(normalized_record)
    embedding_reasoning = build_embedding_reasoning(normalized_record)
    embedding_vector = create_embedding(embedding_text)
    matches = find_department_record_matches(
        normalized_record=normalized_record,
        embedding_vector=embedding_vector,
        limit=request.limit,
    )
    enriched_matches = enrich_department_record_matches(matches)

    top_match = enriched_matches[0] if enriched_matches else None
    if not top_match:
        result_status = "NO_MATCH"
    elif top_match["match_type"] == "hard" or top_match["similarity_score"] > AUTO_MATCH_THRESHOLD:
        result_status = "UBID_MATCHED"
    elif top_match["similarity_score"] >= NEW_BUSINESS_THRESHOLD:
        result_status = "CANDIDATE_MATCH"
    else:
        result_status = "LOW_CONFIDENCE_MATCH"

    return {
        "status": result_status,
        "matched_ubid": top_match.get("ubid") if top_match else None,
        "top_match": top_match,
        "matches": enriched_matches,
        "input": incoming_record,
        "normalized_input": normalized_record,
        "embedding": {
            "text": embedding_text,
            "dimension": len(embedding_vector),
            "reasoning": embedding_reasoning,
        },
        "thresholds": {
            "candidate_match_min_score": NEW_BUSINESS_THRESHOLD,
            "auto_match_min_score": AUTO_MATCH_THRESHOLD,
        },
        "stored": False,
    }
