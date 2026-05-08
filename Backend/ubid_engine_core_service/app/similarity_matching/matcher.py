from app.similarity_matching.models import DepartmentRecordMatch
from app.embeddings import EMBEDDING_SOURCE_FIELDS
from app.vector_storage.milvus_vector_store import (
    EMBEDDING_DIMENSION,
    department_record_id_from_record,
    get_department_record_collection,
    scalar_value,
    source_system_from_record,
)


def _escape_expr_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _hard_match_expr(normalized_record: dict) -> tuple[str, dict[str, str]]:
    available_fields = {}
    expressions = []

    gstin = scalar_value(normalized_record, "normalized_gstin")
    if gstin:
        available_fields["normalized_gstin"] = gstin
        expressions.append(f'normalized_gstin == "{_escape_expr_value(gstin)}"')

    pan = scalar_value(normalized_record, "normalized_pan")
    if pan:
        available_fields["normalized_pan"] = pan
        expressions.append(f'normalized_pan == "{_escape_expr_value(pan)}"')

    department_record_id = department_record_id_from_record(normalized_record)
    source_system = source_system_from_record(normalized_record)
    if department_record_id and source_system:
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


def _match_from_hit(hit, match_type: str, matched_field: str | None = None) -> DepartmentRecordMatch:
    entity = hit.entity
    return DepartmentRecordMatch(
        record_id=entity.get("record_id"),
        data_record_id=entity.get("data_record_id"),
        similarity_score=float(hit.score),
        match_type=match_type,
        matched_field=matched_field,
        embedding_text=entity.get("embedding_text"),
        metadata=entity.get("metadata"),
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
        data_record_id=result.get("data_record_id"),
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
    hard_expr, hard_fields = _hard_match_expr(normalized_record)
    output_fields = ["record_id", "data_record_id", "embedding_text", "metadata"]

    if hard_expr:
        hard_results = collection.query(
            expr=hard_expr,
            output_fields=[
                *output_fields,
                "normalized_gstin",
                "normalized_pan",
                "department_record_id",
                "source_system",
            ],
            limit=limit,
        )
        if hard_results:
            return [
                _match_from_query_result(result, hard_fields)
                for result in hard_results
            ]

    if not _has_vector_search_input(normalized_record):
        return []

    search_results = collection.search(
        data=[embedding_vector],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        limit=limit,
        output_fields=output_fields,
    )
    if not search_results or not search_results[0]:
        return []

    return [
        _match_from_hit(hit, match_type="vector")
        for hit in search_results[0]
    ]


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
