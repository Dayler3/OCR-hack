"""Настройки сервиса. Значения можно переопределять переменными окружения."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


class Settings:
    # --- OCR ---
    # auto: PaddleOCR -> pytesseract -> ошибка с понятным текстом
    ocr_engine: str = _env("OCR_ENGINE", "auto")
    ocr_lang: str = _env("OCR_LANG", "ru")
    # MKLDNN выключен по умолчанию: обход OneDNN-бага paddlepaddle 3.3.x на Windows CPU
    ocr_enable_mkldnn: bool = _env("OCR_ENABLE_MKLDNN", "0") == "1"
    # DPI рендера страниц PDF в растр перед OCR
    pdf_dpi: int = int(_env("PDF_DPI", "200"))
    max_pages: int = int(_env("MAX_PAGES", "10"))

    # --- Функциональные флаги ---
    enable_classifier: bool = _env("ENABLE_CLASSIFIER", "1") == "1"
    enable_ner: bool = _env("ENABLE_NER", "1") == "1"
    enable_embeddings: bool = _env("ENABLE_EMBEDDINGS", "1") == "1"

    # --- Пороги ---
    # ниже — считаем, что Положение не покрывает вопрос (ветка «Ответа нет»)
    rag_relevance_threshold: float = float(_env("RAG_RELEVANCE_THRESHOLD", "0.30"))
    # порог нечёткого совпадения для options/якорей классификатора
    # (падежные окончания дают ~80 при 5-символьных словах)
    fuzz_threshold: int = int(_env("FUZZ_THRESHOLD", "80"))
    # минимальный скор классификатора типа документа
    classify_min_score: float = float(_env("CLASSIFY_MIN_SCORE", "0.3"))

    # --- Пути ---
    schemas_path: Path = BASE_DIR / "configs" / "document_schemas.yaml"
    regulations_path: Path = BASE_DIR / "data" / "regulations.json"
    samples_dir: Path = BASE_DIR / "data" / "samples"

    # --- Ответы ---
    not_found_value: str = "не найдено"
    yes_value: str = "есть"
    no_value: str = "нет"


settings = Settings()
