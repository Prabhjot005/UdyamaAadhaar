import os
import uuid
from dataclasses import dataclass
from functools import lru_cache


DEFAULT_MILVUS_COLLECTION_NAME = "department_record_embeddings"
EMBEDDING_DIMENSION = 384


@dataclass(frozen=True)
class DepartmentRecordMatch:
    record_id: str
    mongo_id: str
    similarity_score: float
    match_type: str
    matched_field: str | None = None
    metadata: dict | None = None


def _milvus_host() -> str:
    return os.getenv("MILVUS_HOST", "localhost")


def _milvus_port() -> str:
    return os.getenv("MILVUS_PORT", "19530")


def _collection_name() -> str:
    return os.getenv("MILVUS_COLLECTION_NAME", DEFAULT_MILVUS_COLLECTION_NAME)


def _record_id(record: dict) -> str:
    for key in ("mongoId", "mongo_id", "id", "recordId", "record_id", "departmentRecordId", "department_record_id"):
        value = record.get(key)
        if value:
            return str(value)

    return str(uuid.uuid4())


def _mongo_id(record: dict) -> str:
    return str(record.get("mongoId") or record.get("mongo_id") or "")


def _scalar_value(record: dict, key: str) -> str:
    return str(record.get(key) or "")


def _escape_expr_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _hard_match_expr(normalized_record: dict) -> tuple[str, dict[str, str]]:
    hard_match_fields = {
        "mongo_id": _mongo_id(normalized_record),
        "normalized_gstin": _scalar_value(normalized_record, "normalized_gstin"),
        "normalized_pincode": _scalar_value(normalized_record, "normalized_pincode"),
        "normalized_pan": _scalar_value(normalized_record, "normalized_pan"),
    }
    available_fields = {
        field_name: value
        for field_name, value in hard_match_fields.items()
        if value
    }
    expr = " or ".join(
        f'{field_name} == "{_escape_expr_value(value)}"'
        for field_name, value in available_fields.items()
    )
    return expr, available_fields


def _connect() -> None:
    from pymilvus import connections

    connections.connect(alias="default", host=_milvus_host(), port=_milvus_port())


def _create_collection():
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema

    fields = [
        FieldSchema(
            name="record_id",
            dtype=DataType.VARCHAR,
            is_primary=True,
            max_length=128,
        ),
        FieldSchema(name="mongo_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="normalized_gstin", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="normalized_pincode", dtype=DataType.VARCHAR, max_length=16),
        FieldSchema(name="normalized_pan", dtype=DataType.VARCHAR, max_length=16),
        FieldSchema(name="embedding_text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="metadata", dtype=DataType.JSON),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=EMBEDDING_DIMENSION,
        ),
    ]
    schema = CollectionSchema(fields=fields, description="Department record embeddings")
    collection = Collection(name=_collection_name(), schema=schema)
    collection.create_index(
        field_name="embedding",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        },
    )
    return collection


def _validate_collection_schema(collection) -> None:
    field_names = {field.name for field in collection.schema.fields}
    required_fields = {
        "record_id",
        "mongo_id",
        "normalized_gstin",
        "normalized_pincode",
        "normalized_pan",
        "embedding_text",
        "metadata",
        "embedding",
    }
    missing_fields = required_fields - field_names

    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise RuntimeError(
            f"Milvus collection '{_collection_name()}' is missing required field(s): {missing}. "
            "Drop/recreate the collection or migrate it before inserting records."
        )


@lru_cache(maxsize=1)
def _get_collection():
    from pymilvus import Collection, utility

    _connect()

    collection_name = _collection_name()
    if utility.has_collection(collection_name):
        collection = Collection(collection_name)
        _validate_collection_schema(collection)
    else:
        collection = _create_collection()

    collection.load()
    return collection


def _match_from_hit(hit, match_type: str, matched_field: str | None = None) -> DepartmentRecordMatch:
    entity = hit.entity
    return DepartmentRecordMatch(
        record_id=entity.get("record_id"),
        mongo_id=entity.get("mongo_id"),
        similarity_score=float(hit.score),
        match_type=match_type,
        matched_field=matched_field,
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
        mongo_id=result.get("mongo_id"),
        similarity_score=1.0,
        match_type="hard",
        matched_field=matched_field,
        metadata=result.get("metadata"),
    )


def find_department_record_match(
    normalized_record: dict,
    embedding_vector: list[float],
    limit: int = 1,
) -> DepartmentRecordMatch | None:
    if len(embedding_vector) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected embedding dimension {EMBEDDING_DIMENSION}, got {len(embedding_vector)}"
        )

    collection = _get_collection()
    hard_expr, hard_fields = _hard_match_expr(normalized_record)
    output_fields = ["record_id", "mongo_id", "metadata"]

    if hard_expr:
        hard_results = collection.query(
            expr=hard_expr,
            output_fields=[
                *output_fields,
                "normalized_gstin",
                "normalized_pincode",
                "normalized_pan",
            ],
            limit=1,
        )
        if hard_results:
            return _match_from_query_result(hard_results[0], hard_fields)

    search_results = collection.search(
        data=[embedding_vector],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        limit=limit,
        output_fields=output_fields,
    )
    if not search_results or not search_results[0]:
        return None

    return _match_from_hit(search_results[0][0], match_type="vector")


def store_department_record_embedding(
    original_record: dict,
    normalized_record: dict,
    embedding_text: str,
    embedding_vector: list[float],
) -> str:
    if len(embedding_vector) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected embedding dimension {EMBEDDING_DIMENSION}, got {len(embedding_vector)}"
        )

    record_id = _record_id(original_record)
    mongo_id = _mongo_id(original_record)
    normalized_gstin = _scalar_value(normalized_record, "normalized_gstin")
    normalized_pincode = _scalar_value(normalized_record, "normalized_pincode")
    normalized_pan = _scalar_value(normalized_record, "normalized_pan")
    collection = _get_collection()
    collection.insert(
        [
            [record_id],
            [mongo_id],
            [normalized_gstin],
            [normalized_pincode],
            [normalized_pan],
            [embedding_text[:65535]],
            [normalized_record],
            [embedding_vector],
        ]
    )
    collection.flush()
    return record_id
