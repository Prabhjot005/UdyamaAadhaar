import os
import re
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.embeddings import create_embedding
from app.vector_storage import EMBEDDING_DIMENSION


DEFAULT_EVENT_CATEGORY_COLLECTION_NAME = "event_category_master"


class EventCategoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_category: str | None = Field(default=None, alias="eventCategory")
    descriptive_vector_text: str | None = Field(default=None, alias="descriptiveVectorText")
    base_weight: float = Field(alias="baseWeight")
    recommended_decay_constant: float = Field(alias="recommendedDecayConstant")

    @model_validator(mode="before")
    @classmethod
    def accept_column_names(cls, values):
        if not isinstance(values, dict):
            return values

        aliases = {
            "Event Category": "eventCategory",
            "Descriptive Vector Text": "descriptiveVectorText",
            "Base Weight": "baseWeight",
            "Recommended Decay Constant": "recommendedDecayConstant",
            "event_category": "eventCategory",
            "descriptive_vector_text": "descriptiveVectorText",
            "base_weight": "baseWeight",
            "recommended_decay_constant": "recommendedDecayConstant",
        }
        return {aliases.get(key, key): value for key, value in values.items()}

    @model_validator(mode="after")
    def validate_text(self):
        if not (self.event_category or "").strip():
            raise ValueError("eventCategory is required")
        if not (self.descriptive_vector_text or "").strip():
            raise ValueError("descriptiveVectorText is required")
        return self


class EventCategorySeedRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    categories: list[EventCategoryItem]

    @model_validator(mode="before")
    @classmethod
    def accept_list_payload(cls, values):
        if isinstance(values, list):
            return {"categories": values}
        return values


class EventCategoryMatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    event_category: str | None = Field(default=None, alias="eventCategory")
    descriptive_vector_text: str | None = Field(default=None, alias="descriptiveVectorText")
    text: str | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_column_names(cls, values):
        if not isinstance(values, dict):
            return values

        aliases = {
            "Event Category": "eventCategory",
            "Descriptive Vector Text": "descriptiveVectorText",
            "event_category": "eventCategory",
            "descriptive_vector_text": "descriptiveVectorText",
        }
        return {aliases.get(key, key): value for key, value in values.items()}


def _milvus_host() -> str:
    return os.getenv("MILVUS_HOST", "localhost")


def _milvus_port() -> str:
    return os.getenv("MILVUS_PORT", "19530")


def _collection_name() -> str:
    return os.getenv("MILVUS_EVENT_CATEGORY_COLLECTION_NAME", DEFAULT_EVENT_CATEGORY_COLLECTION_NAME)


def _connect_to_milvus() -> None:
    from pymilvus import connections

    connections.connect(alias="default", host=_milvus_host(), port=_milvus_port())


def _category_id(event_category: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", event_category.strip().lower())
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:128] or "event_category"


def _embedding_text(event_category: str, descriptive_vector_text: str) -> str:
    return f"Event Category: {event_category.strip()} | Description: {descriptive_vector_text.strip()}"


def _escape_expr_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _create_collection():
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema

    fields = [
        FieldSchema(name="category_id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
        FieldSchema(name="event_category", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="descriptive_vector_text", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="base_weight", dtype=DataType.DOUBLE),
        FieldSchema(name="recommended_decay_constant", dtype=DataType.DOUBLE),
        FieldSchema(name="embedding_text", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIMENSION),
    ]
    schema = CollectionSchema(fields=fields, description="Event category master vectors")
    collection = Collection(name=_collection_name(), schema=schema)
    collection.create_index(
        field_name="embedding",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 64},
        },
    )
    return collection


def _validate_collection_schema(collection) -> None:
    field_names = {field.name for field in collection.schema.fields}
    required_fields = {
        "category_id",
        "event_category",
        "descriptive_vector_text",
        "base_weight",
        "recommended_decay_constant",
        "embedding_text",
        "embedding",
    }
    missing_fields = required_fields - field_names
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise RuntimeError(f"Milvus collection '{_collection_name()}' is missing required field(s): {missing}")


@lru_cache(maxsize=1)
def get_event_category_collection():
    from pymilvus import Collection, utility

    _connect_to_milvus()
    collection_name = _collection_name()
    if utility.has_collection(collection_name):
        collection = Collection(collection_name)
        _validate_collection_schema(collection)
    else:
        collection = _create_collection()

    collection.load()
    return collection


def seed_event_category_master(request: EventCategorySeedRequest) -> dict[str, Any]:
    collection = get_event_category_collection()
    inserted = 0
    updated = 0

    for category in request.categories:
        event_category = category.event_category.strip()
        description = category.descriptive_vector_text.strip()
        category_id = _category_id(event_category)
        embedding_text = _embedding_text(event_category, description)
        embedding = create_embedding(embedding_text)

        existing = collection.query(
            expr=f'category_id == "{_escape_expr_value(category_id)}"',
            output_fields=["category_id"],
            limit=1,
        )
        if existing:
            collection.delete(expr=f'category_id == "{_escape_expr_value(category_id)}"')
            updated += 1
        else:
            inserted += 1

        collection.insert(
            [
                [category_id],
                [event_category],
                [description],
                [category.base_weight],
                [category.recommended_decay_constant],
                [embedding_text[:4096]],
                [embedding],
            ]
        )

    collection.flush()
    collection.load()
    return {
        "collection": _collection_name(),
        "received": len(request.categories),
        "inserted": inserted,
        "updated": updated,
    }


def match_event_category(request: EventCategoryMatchRequest) -> dict[str, Any] | None:
    match_text = request.text or _embedding_text(
        request.event_category or "",
        request.descriptive_vector_text or request.event_category or "",
    )
    embedding = create_embedding(match_text)
    collection = get_event_category_collection()
    search_results = collection.search(
        data=[embedding],
        anns_field="embedding",
        param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        limit=1,
        output_fields=[
            "category_id",
            "event_category",
            "descriptive_vector_text",
            "base_weight",
            "recommended_decay_constant",
            "embedding_text",
        ],
    )
    if not search_results or not search_results[0]:
        return None

    hit = search_results[0][0]
    entity = hit.entity
    return {
        "category_id": entity.get("category_id"),
        "event_category": entity.get("event_category"),
        "descriptive_vector_text": entity.get("descriptive_vector_text"),
        "base_weight": entity.get("base_weight"),
        "recommended_decay_constant": entity.get("recommended_decay_constant"),
        "similarity_score": float(hit.score),
        "embedding_text": entity.get("embedding_text"),
        "input_text": match_text,
    }
