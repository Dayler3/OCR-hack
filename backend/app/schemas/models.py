"""Pydantic v2 схемы ответа API. Контракт зафиксирован в PLAN.md §5."""
from typing import Dict, List, Optional, Literal

from pydantic import BaseModel, Field

BBox = List[int]  # [x1, y1, x2, y2] в координатах препроцесснутой страницы

VerdictStatus = Literal["OK", "MISSING_FIELDS", "NO_INFO"]


class FieldItem(BaseModel):
    key: str
    label: str
    value: str = "не найдено"
    bbox: Optional[BBox] = None
    page: int = 0
    source: str = "schema"  # regex | ner_person | options | anchor_after | cv | schema


class PageInfo(BaseModel):
    """Препроцесснутая страница — единая система координат для OCR и BBox."""

    width: int
    height: int
    image_b64: Optional[str] = None  # PNG в base64; отключается флагом для batch_eval


class Verdict(BaseModel):
    status: VerdictStatus
    text: str
    rule_source: Optional[str] = None


class AnalyzeResponse(BaseModel):
    document_type: Optional[str] = None
    document_name: str = "Документ"
    classifier_confidence: Optional[float] = None
    pages: List[PageInfo] = Field(default_factory=list)
    fields: List[FieldItem] = Field(default_factory=list)
    verdict: Verdict
    timings_ms: Dict[str, int] = Field(default_factory=dict)


class SchemaFieldInfo(BaseModel):
    key: str
    label: str


class SchemaInfo(BaseModel):
    key: str
    name: str
    anchors: List[str] = Field(default_factory=list)
    fields: List[SchemaFieldInfo] = Field(default_factory=list)
