from difflib import SequenceMatcher

from app.similarity_matching.models import DepartmentRecordMatch
from app.embeddings import EMBEDDING_SOURCE_FIELDS
from app.vector_storage.milvus_vector_store import (
    EMBEDDING_DIMENSION,
    collection_field_names,
    department_record_id_from_record,
    get_department_record_collection,
    scalar_value,
    source_system_from_record,
)


NAME_SCORE_WEIGHT = 0.65
PINCODE_SCORE_WEIGHT = 0.25
ADDRESS_SCORE_WEIGHT = 0.10
VECTOR_SEARCH_OVERSAMPLE_FACTOR = 3
VECTOR_SEARCH_MIN_CANDIDATES = 20


def _escape_expr_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _hard_match_expr(normalized_record: dict, field_names: set[str]) -> tuple[str, dict[str, str]]:
    available_fields = {}
    expressions = []

    gstin = scalar_value(normalized_record, "normalized_gstin")
    if gstin and "normalized_gstin" in field_names:
        available_fields["normalized_gstin"] = gstin
        expressions.append(f'normalized_gstin == "{_escape_expr_value(gstin)}"')

    pan = scalar_value(normalized_record, "normalized_pan")
    if pan and "normalized_pan" in field_names:
        available_fields["normalized_pan"] = pan
        expressions.append(f'normalized_pan == "{_escape_expr_value(pan)}"')

    department_record_id = department_record_id_from_record(normalized_record)
    source_system = source_system_from_record(normalized_record)
    if department_record_id and source_system and {"department_record_id", "source_system"}.issubset(field_names):
        available_fields["department_record_id"] = department_record_id
        available_fields["source_system"] = source_system
        expressions.append(
            f'(department_record_id == "{_escape_expr_value(department_record_id)}" '
            f'and source_system == "{_escape_expr_value(source_system)}")'
        )

    expr = " or ".join(expressions)
    return expr, available_fields


def _has_vector_search_input(normalized_record: dict) -> bool:
    return any(normalized_record.get(field) not in (None, "", []) for field in EMBEDDING_SOURCE_FIELDS)


def _clean_value(value) -> str:
    return str(value or "").strip().upper()


def _text_similarity(left, right) -> float:
    left_value = _clean_value(left)
    right_value = _clean_value(right)
    if not left_value or not right_value:
        return 0.0
    return SequenceMatcher(None, left_value, right_value).ratio()


def _pincode_similarity(left, right) -> float:
    left_value = _clean_value(left)
    right_value = _clean_value(right)
    if not left_value or not right_value:
        return 0.0
    return 1.0 if left_value == right_value else 0.0


def _address_similarity(incoming_record: dict, matched_record: dict) -> float:
    incoming_addresses = [
        incoming_record.get("normalized_address"),
        incoming_record.get("normalized_other_address"),
    ]
    matched_addresses = [
        matched_record.get("normalized_address"),
        matched_record.get("normalized_other_address"),
    ]
    return max(
        (
            _text_similarity(incoming_address, matched_address)
            for incoming_address in incoming_addresses
            for matched_address in matched_addresses
        ),
        default=0.0,
    )


def _weighted_vector_score(incoming_record: dict, matched_record: dict) -> tuple[float, dict[str, float]]:
    name_score = _text_similarity(
        incoming_record.get("normalized_name"),
        matched_record.get("normalized_name"),
    )
    pincode_score = _pincode_similarity(
        incoming_record.get("normalized_pincode"),
        matched_record.get("normalized_pincode"),
    )
    address_score = _address_similarity(incoming_record, matched_record)
    weighted_score = (
        (NAME_SCORE_WEIGHT * name_score)
        + (PINCODE_SCORE_WEIGHT * pincode_score)
        + (ADDRESS_SCORE_WEIGHT * address_score)
    )
    return weighted_score, {
        "name_score": name_score,
        "pincode_score": pincode_score,
        "address_score": address_score,
        "name_weight": NAME_SCORE_WEIGHT,
        "pincode_weight": PINCODE_SCORE_WEIGHT,
        "address_weight": ADDRESS_SCORE_WEIGHT,
    }


def _match_from_hit(hit, incoming_record: dict, match_type: str, matched_field: str | None = None) -> DepartmentRecordMatch:
    entity = hit.entity
    metadata = entity.get("metadata") or {}
    metadata = metadata if isinstance(metadata, dict) else {}
    weighted_score, scoring_details = _weighted_vector_score(incoming_record, metadata)
    enriched_metadata = {
        **metadata,
        "weighted_similarity": {
            **scoring_details,
            "milvus_cosine_score": float(hit.score),
            "final_similarity_score": weighted_score,
            "formula": "0.65 * name_score + 0.25 * pincode_score + 0.10 * address_score",
        },
    }
    return DepartmentRecordMatch(
        record_id=entity.get("record_id"),
        data_record_id=entity.get("data_record_id") or entity.get("mongo_id"),
        similarity_score=weighted_score,
        match_type=match_type,
        matched_field=matched_field,
        embedding_text=entity.get("embedding_text"),
        metadata=enriched_metadata,
    )


def _match_from_query_result(
    result: dict,
    incoming_fields: dict[str, str],
) -> DepartmentRecordMatch:
    matched_field = next(
        (
            field_name
            for field_name, incoming_value in incoming_fields.items()
            if result.get(field_name) == incoming_value
        ),
        None,
    )
    return DepartmentRecordMatch(
        record_id=result.get("record_id"),
        data_record_id=result.get("data_record_id") or result.get("mongo_id"),
        similarity_score=1.0,
        match_type="hard",
        matched_field=matched_field,
        embedding_text=result.get("embedding_text"),
        metadata=result.get("metadata"),
    )


def find_department_record_matches(
    normalized_record: dict,
    embedding_vector: list[float],
    limit: int = 5,
) -> list[DepartmentRecordMatch]:
    if len(embedding_vector) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected embedding dimension {EMBEDDING_DIMENSION}, got {len(embedding_vector)}"
        )

    collection = get_department_record_collection()
    field_names = collection_field_names(collection)
    hard_expr, hard_fields = _hard_match_expr(normalized_record, field_names)
    data_id_field = "data_record_id" if "data_record_id" in field_names else "mongo_id"
    output_fields = ["record_id", data_id_field, "embedding_text", "metadata"]

    if hard_expr:
        hard_output_fields = [
            *output_fields,
            *[
                field
                for field in (
                    "normalized_gstin",
                    "normalized_pan",
                    "department_record_id",
                    "source_system",
                )
                if field in field_names
            ],
        ]
        hard_results = collection.query(
            expr=hard_expr,
            output_fields=hard_output_fields,
            limit=limit,
        )
        if hard_results:
            return [
                _match_from_query_result(result, hard_fields)
                for result in hard_results
            ]

    if not _has_vector_search_input(normalized_record):
        return []

    vector_candidate_limit = max(limit * VECTOR_SEARCH_OVERSAMPLE_FACTOR, VECTOR_SEARCH_MIN_CANDIDATES)
    search_results = collection.search(
        data=[embedding_vector],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        limit=vector_candidate_limit,
        output_fields=output_fields,
    )
    if not search_results or not search_results[0]:
        return []

    weighted_matches = [
        _match_from_hit(hit, normalized_record, match_type="vector")
        for hit in search_results[0]
    ]
    return sorted(weighted_matches, key=lambda match: match.similarity_score, reverse=True)[:limit]


def find_department_record_match(
    normalized_record: dict,
    embedding_vector: list[float],
    limit: int = 1,
) -> DepartmentRecordMatch | None:
    matches = find_department_record_matches(
        normalized_record=normalized_record,
        embedding_vector=embedding_vector,
        limit=limit,
    )
    return matches[0] if matches else None
