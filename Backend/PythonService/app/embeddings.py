from functools import lru_cache


EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_SOURCE_FIELDS = (
    "normalized_name",
    "normalized_address",
    "normalized_pincode",
)


@lru_cache(maxsize=1)
def _get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def create_embedding(text: str) -> list[float]:
    if not text.strip():
        return []

    model = _get_embedding_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def build_embedding_text(normalized_record: dict) -> str:
    return " | ".join(
        f"{key}: {value}"
        for key in EMBEDDING_SOURCE_FIELDS
        if (value := normalized_record.get(key)) not in (None, "", [])
    )


def build_embedding_reasoning(normalized_record: dict) -> dict:
    included_fields = {
        key: normalized_record.get(key)
        for key in EMBEDDING_SOURCE_FIELDS
        if normalized_record.get(key) not in (None, "", [])
    }
    excluded_fields = sorted(
        key
        for key, value in normalized_record.items()
        if key not in EMBEDDING_SOURCE_FIELDS and value not in (None, "", [])
    )

    return {
        "model": EMBEDDING_MODEL_NAME,
        "source_fields": list(EMBEDDING_SOURCE_FIELDS),
        "included_fields": included_fields,
        "excluded_fields": excluded_fields,
        "reason": (
            "Vector similarity uses normalized business name, normalized address, "
            "and normalized pincode only. Hard identifiers such as Mongo ID, GSTIN, "
            "PAN, and other metadata are excluded from embeddings and handled through "
            "scalar matching or decision metadata."
        ),
    }
