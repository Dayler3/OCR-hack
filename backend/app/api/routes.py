"""REST API: /api/analyze, /api/schemas, /api/health."""
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.extractor import SchemaRegistry
from app.schemas.models import AnalyzeResponse, SchemaFieldInfo, SchemaInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

_pipeline = None  # ленивый синглтон: тяжёлые модели грузятся при первом /api/analyze


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from app.core.pipeline import ProcessPipeline

        _pipeline = ProcessPipeline()
    return _pipeline


def set_pipeline(pipeline) -> None:
    """Точка внедрения мока для тестов."""
    global _pipeline
    _pipeline = pipeline


@router.get("/health")
def health() -> dict:
    from app.core.ocr_engine import OcrEngine

    ocr = OcrEngine()
    try:
        ocr._ensure_engine()
        ocr_status = ocr.engine_name
    except Exception:
        ocr_status = "недоступен (pip install -r requirements-ml.txt)"
    return {
        "status": "ok",
        "ocr_engine": ocr_status,
        "schemas_loaded": len(SchemaRegistry().doc_types()),
    }


@router.get("/schemas", response_model=list[SchemaInfo])
def schemas() -> list[SchemaInfo]:
    registry = SchemaRegistry()
    return [
        SchemaInfo(
            key=doc_type,
            name=registry.display_name(doc_type),
            anchors=registry.anchors(doc_type),
            fields=[SchemaFieldInfo(key=k, label=v.get("label", k))
                    for k, v in registry.fields(doc_type).items()],
        )
        for doc_type in registry.doc_types()
    ]


ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".pdf"}


def _fix_mojibake(value: str) -> str:
    """multipart-поля без charset python-multipart декодирует как latin-1, а
    клиенты шлют UTF-8 (браузер) или CP1251 (curl в Windows-консоли).
    Возвращаем исходные байты и пробуем utf-8 → cp1251 → cp866; принимаем
    вариант, в котором появилась кириллица."""
    if any("\u0400" <= ch <= "\u04FF" for ch in value):
        return value  # кириллица уже на месте
    try:
        raw = value.encode("latin-1")
    except UnicodeEncodeError:
        return value
    for encoding in ("utf-8", "cp1251", "cp866"):
        try:
            fixed = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        if any("\u0400" <= ch <= "\u04FF" for ch in fixed):
            return fixed
    return value


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(...),
    question: str = Form(default=""),
    doc_type: Optional[str] = Form(default=None),
) -> AnalyzeResponse:
    question = _fix_mojibake(question)
    doc_type = _fix_mojibake(doc_type) if doc_type else doc_type
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, f"Допустимые форматы: JPG, PNG, PDF (получен {suffix or 'без расширения'})")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        return get_pipeline().run(tmp_path, question=question, doc_type=doc_type)
    except FileNotFoundError as exc:
        raise HTTPException(400, f"Файл не найден: {exc}") from exc
    except Exception as exc:  # OCR-движок и т.п. — 502 с понятным текстом
        logger.exception("Ошибка обработки документа")
        raise HTTPException(502, str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
