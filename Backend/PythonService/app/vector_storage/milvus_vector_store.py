import os
import uuid
from functools import lru_cache


DEFAULT_MILVUS_COLLECTION_NAME = "department_record_embeddings"
EMBEDDING_DIMENSION = 384


def _milvus_host() -> str:
    return os.getenv("MILVUS_HOST", "localhost")


def _milvus_port() -> str:
    return os.getenv("MILVUS_PORT", "19530")


def _collection_name() -> str:
    return os.getenv("MILVUS_COLLECTION_NAME", DEFAULT_MILVUS_COLLECTION_NAME)


def record_id_from_record(record: dict) -> str:
    for key in ("mongoId", "mongo_id", "id", "recordId", "record_id", "departmentRecordId", "department_record_id"):
        value = record.get(key)
        if value:
            return str(value)

    return str(uuid.uuid4())


def mongo_id_from_record(record: dict) -> str:
    return str(record.get("mongoId") or record.get("mongo_id") or "")


def scalar_value(record: dict, key: str) -> str:
    return str(record.get(key) or "")


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
    mongo_id = mongo_id_from_record(original_record)
    normalized_gstin = scalar_value(normalized_record, "normalized_gstin")
    normalized_pincode = scalar_value(normalized_record, "normalized_pincode")
    normalized_pan = scalar_value(normalized_record, "normalized_pan")
    collection = get_department_record_collection()
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
