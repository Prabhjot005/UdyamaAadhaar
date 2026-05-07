from functools import lru_cache


EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


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
        for key, value in normalized_record.items()
        if value not in (None, "", [])
    )
