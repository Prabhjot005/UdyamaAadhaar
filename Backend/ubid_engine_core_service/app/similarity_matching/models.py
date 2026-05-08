from dataclasses import dataclass


@dataclass(frozen=True)
class DepartmentRecordMatch:
    record_id: str
    data_record_id: str
    similarity_score: float
    match_type: str
    matched_field: str | None = None
    embedding_text: str | None = None
    metadata: dict | None = None
