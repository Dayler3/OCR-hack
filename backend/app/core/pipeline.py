"""Оркестратор: файл + вопрос (+ тип документа) → AnalyzeResponse.

Единая точка входа для REST API (/api/analyze) и пакетной оценки
(batch_eval.py). Последовательность этапов — PLAN.md §3:

загрузка → препроцессинг → OCR → (классификация) → извлечение полей
→ RAG-поиск пункта Положения → вердикт одной из 3 веток.
"""
import base64
import logging
import time
from pathlib import Path
from typing import List, Optional, Union

import cv2

from app.config import settings
from app.core.classifier import classify_document
from app.core.extractor import SchemaRegistry, extract_fields
from app.core.ocr_engine import OcrEngine, OcrPage, load_document_pages
from app.core.preprocessor import deskew_and_enhance
from app.core.rag_engine import RagEngine
from app.core.validator import evaluate_document_rules, no_info_verdict
from app.schemas.models import AnalyzeResponse, PageInfo, Verdict

logger = logging.getLogger(__name__)


class ProcessPipeline:
    def __init__(self, include_page_images: bool = True):
        self.registry = SchemaRegistry()
        self.rag = RagEngine()
        self.ocr = OcrEngine()
        self.include_page_images = include_page_images

    # --- этапы ---

    def _preprocess_and_ocr(self, file_path: Union[str, Path]) -> List[OcrPage]:
        pages: List[OcrPage] = []
        for i, raw in enumerate(load_document_pages(file_path)[: settings.max_pages]):
            t0 = time.perf_counter()
            enhanced = deskew_and_enhance(raw)
            page = OcrPage(
                page_index=i,
                width=enhanced.image.shape[1],
                height=enhanced.image.shape[0],
                image=enhanced.image,
            )
            self.ocr.recognize_page(page)
            logger.debug("страница %d: препроцессинг+OCR за %.0f мс (поворот %.1f°)",
                         i, (time.perf_counter() - t0) * 1000, enhanced.angle)
            pages.append(page)
        return pages

    def _page_info(self, page: OcrPage) -> PageInfo:
        image_b64 = None
        if self.include_page_images:
            ok, buf = cv2.imencode(".png", page.image)
            if ok:
                image_b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        return PageInfo(width=page.width, height=page.height, image_b64=image_b64)

    # --- публичный API ---

    def run(
        self,
        file_path: Union[str, Path],
        question: str,
        doc_type: Optional[str] = None,
    ) -> AnalyzeResponse:
        timings: dict = {}
        t_start = time.perf_counter()

        # 1-2. Препроцессинг + OCR (объединены: постранично)
        pages = self._preprocess_and_ocr(file_path)
        timings["preprocess_ocr"] = int((time.perf_counter() - t_start) * 1000)

        # 3. Тип документа: ручной выбор или автоопределение
        confidence = None
        t0 = time.perf_counter()
        if doc_type and self.registry.get(doc_type):
            pass  # пользователь выбрал вручную
        elif settings.enable_classifier:
            doc_type, confidence = classify_document(pages, self.registry, question=question)
        timings["classify"] = int((time.perf_counter() - t0) * 1000)

        if not doc_type or not self.registry.get(doc_type):
            doc_types = self.registry.doc_types()
            if doc_types:
                doc_type = doc_types[0]
                confidence = confidence or settings.classify_min_score
            else:
                return AnalyzeResponse(
                    document_type=None,
                    document_name="Неизвестный тип документа",
                    classifier_confidence=confidence,
                    pages=[self._page_info(p) for p in pages],
                    fields=[],
                    verdict=no_info_verdict(question),
                    timings_ms=timings,
                )

        # 4. Извлечение полей по YAML-схеме
        t0 = time.perf_counter()
        fields = extract_fields(doc_type, pages, self.registry)
        timings["extract"] = int((time.perf_counter() - t0) * 1000)

        # 5. RAG: пункт Положения по вопросу (и типу документа)
        t0 = time.perf_counter()
        rule = self.rag.retrieve(question, doc_type=doc_type)
        timings["rag"] = int((time.perf_counter() - t0) * 1000)

        # 6. Вердикт: NO_INFO | MISSING_FIELDS | OK
        if rule is None:
            verdict = no_info_verdict(question)
        else:
            verdict = evaluate_document_rules(
                self.registry.display_name(doc_type),
                {f.key: f for f in fields},
                rule,
            )

        return AnalyzeResponse(
            document_type=doc_type,
            document_name=self.registry.display_name(doc_type),
            classifier_confidence=confidence,
            pages=[self._page_info(p) for p in pages],
            fields=fields,
            verdict=verdict,
            timings_ms=timings,
        )
