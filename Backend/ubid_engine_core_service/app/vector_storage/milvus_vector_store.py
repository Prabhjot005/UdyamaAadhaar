import os
import uuid
import logging
from functools import lru_cache


logger = logging.getLogger("ubid-engine-core.vector-storage")

DEFAULT_MILVUS_COLLECTION_NAME = "department_record_embeddings"
EMBEDDING_DIMENSION = 384


def _milvus_host() -> str:
    return os.getenv("MILVUS_HOST", "localhost")


def _milvus_port() -> str:
    return os.getenv("MILVUS_PORT", "19530")


def _collection_name() -> str:
    return os.getenv("MILVUS_COLLECTION_NAME", DEFAULT_MILVUS_COLLECTION_NAME)


def record_id_from_record(record: dict) -> str:
    for key in ("dataRecordId", "data_record_id", "recordId", "record_id", "mongoId", "mongo_id", "id", "departmentRecordId", "department_record_id"):
        value = record.get(key)
        if value:
            return str(value)

    return str(uuid.uuid4())


def data_record_id_from_record(record: dict) -> str:
    return str(record.get("dataRecordId") or record.get("data_record_id") or record.get("recordId") or record.get("record_id") or record.get("mongoId") or record.get("mongo_id") or "")


def department_record_id_from_record(record: dict) -> str:
    return str(record.get("departmentRecordId") or record.get("department_record_id") or record.get("deptRecordId") or record.get("dept_record_id") or "")


def source_system_from_record(record: dict) -> str:
    return str(record.get("sourceSystem") or record.get("source_system") or record.get("source") or "")


def scalar_value(record: dict, key: str) -> str:
    return str(record.get(key) or "")


def _escape_expr_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def connect_to_milvus() -> None:
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
        FieldSchema(name="data_record_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="department_record_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="source_system", dtype=DataType.VARCHAR, max_length=128),
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
def get_department_record_collection():
    from pymilvus import Collection, utility

    connect_to_milvus()

    collection_name = _collection_name()
    if utility.has_collection(collection_name):
        collection = Collection(collection_name)
        _validate_collection_schema(collection)
    else:
        collection = _create_collection()

    collection.load()
    return collection


def collection_field_names(collection=None) -> set[str]:
    collection = collection or get_department_record_collection()
    return {field.name for field in collection.schema.fields}


def find_existing_record_id_by_data_record_id(data_record_id: str) -> str | None:
    if not data_record_id:
        return None

    collection = get_department_record_collection()
    results = collection.query(
        expr=f'data_record_id == "{_escape_expr_value(data_record_id)}"',
        output_fields=["record_id"],
        limit=1,
    )
    if not results:
        return None

    return results[0].get("record_id")


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

    record_id = record_id_from_record(original_record)
    data_record_id = data_record_id_from_record(original_record)
    department_record_id = department_record_id_from_record(normalized_record)
    source_system = source_system_from_record(normalized_record)
    existing_record_id = find_existing_record_id_by_data_record_id(data_record_id)
    if existing_record_id:
        logger.info(
            "Skipping Milvus insert because data_record_id already exists: data_record_id=%s; record_id=%s",
            data_record_id,
            existing_record_id,
        )
        return existing_record_id

    normalized_gstin = scalar_value(normalized_record, "normalized_gstin")
    normalized_pincode = scalar_value(normalized_record, "normalized_pincode")
    normalized_pan = scalar_value(normalized_record, "normalized_pan")
    collection = get_department_record_collection()
    collection.insert(
        [
            [record_id],
            [data_record_id],
            [department_record_id],
            [source_system],
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
