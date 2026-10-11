"""Извлечение полей документа по YAML-схеме (§8.1 ТЗ).

Типы полей:
  ner_person        — regex из схемы; при промахе Natasha NER (если установлена)
  regex             — группа(ы) регулярного выражения, склеиваются join_groups
  options           — нечёткий поиск одного из вариантов (RapidFuzz)
  anchor_after      — текст после якорного слова до конца строки
  cv_stamp_and_sign / cv_signature_only — CV-детекторы («есть»/«нет»)

Все bbox возвращаются в координатах препроцесснутых страниц (PLAN.md §3).
Ненайденное поле строго равно settings.not_found_value.
"""
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml
from rapidfuzz import fuzz

from app.config import settings
from app.core.cv_detectors import detect_signature, detect_stamp
from app.core.ocr_engine import OcrPage
from app.schemas.models import FieldItem

logger = logging.getLogger(__name__)

_ws_re = re.compile(r"\s+")
_trailing_punct_re = re.compile(r"[\s,;:.\u2011]+$")


class SchemaRegistry:
    """Загрузка configs/document_schemas.yaml; новые типы — без правок кода."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or settings.schemas_path)
        with open(self.path, "r", encoding="utf-8") as f:
            self._docs: Dict[str, dict] = yaml.safe_load(f)["documents"]

    def doc_types(self) -> List[str]:
        return list(self._docs)

    def get(self, doc_type: str) -> Optional[dict]:
        return self._docs.get(doc_type)

    def display_name(self, doc_type: str) -> str:
        return self._docs.get(doc_type, {}).get("name", doc_type)

    def anchors(self, doc_type: str) -> List[str]:
        return self._docs.get(doc_type, {}).get("anchors", [])

    def fields(self, doc_type: str) -> Dict[str, dict]:
        return self._docs.get(doc_type, {}).get("fields", {})


# --- Natasha NER (ленивый синглтон, опционально) ---

_ner_tagger = None
_ner_failed = False


def _get_ner():
    global _ner_tagger, _ner_failed
    if _ner_failed or not settings.enable_ner:
        return None
    if _ner_tagger is None:
        try:
            from natasha import Doc, NewsEmbedding, NewsNERTagger, Segmenter

            _ner_tagger = (
                Segmenter(),
                NewsNERTagger(NewsEmbedding()),
            )
        except Exception as exc:
            logger.info("Natasha NER недоступен (regex-фолбэк): %s", exc)
            _ner_failed = True
            return None
    return _ner_tagger


def _ner_find_person(text: str) -> Optional[str]:
    bundle = _get_ner()
    if bundle is None:
        return None
    segmenter, tagger = bundle
    from natasha import Doc

    doc = Doc(text[:5000])
    doc.segment(segmenter)
    doc.tag_ner(tagger)
    for span in doc.spans:
        if span.type != "PER":
            continue
        tokens = span.text.split()
        if 2 <= len(tokens) <= 3 and all(t and (t[0].isupper() or t[0].isalpha()) for t in tokens):
            return _ws_re.sub(" ", span.text).strip()
    return None


# --- Поиск по страницам с маппингом позиции матча на bbox строк ---

def _line_spans(page: OcrPage) -> List[Tuple[int, int, List[int]]]:
    spans, pos = [], 0
    for line in page.lines:
        spans.append((pos, pos + len(line.text), line.bbox))
        pos += len(line.text) + 1  # "\n"
    return spans


def _search_regex(
    pages: List[OcrPage],
    pattern: re.Pattern,
    join_sep: str,
    take_last: bool = False,
    swap_groups: bool = False,
):
    """Ищет шаблон постранично; возвращает (groups, bbox, page_index) или None.
    take_last=True — последнее совпадение в документе (для application_date:
    дата подачи обычно стоит последней)."""
    found = None
    for page in pages:
        text = page.text
        for m in pattern.finditer(text):
            spans = _line_spans(page)
            boxes = [bbox for s, e, bbox in spans if e >= m.start() and s <= m.end()]
            bbox = [
                min(b[0] for b in boxes), min(b[1] for b in boxes),
                max(b[2] for b in boxes), max(b[3] for b in boxes),
            ] if boxes else None
            groups = [g for g in m.groups() if g]
            if not groups:
                groups = [m.group(0)]
            if swap_groups and len(groups) >= 2:
                groups = list(reversed(groups))
            value = join_sep.join(_ws_re.sub(" ", g).strip() for g in groups) if groups else ""
            found = (value.strip(" ,;:."), bbox, page.page_index)
            if not take_last:
                return found
    return found


_num_only_re = re.compile(r"№\s*([A-Za-zА-Яа-я0-9\-/]+)")
_date_only_re = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")


def _fallback_number_and_date(pages: List[OcrPage]):
    """Когда дата (слева) и номер № (справа) в шапке бланка распознаны
    OCR как отдельные блоки на разных строках."""
    num_hit = _search_regex(pages, _num_only_re, " ")
    date_hit = _search_regex(pages, _date_only_re, " ")
    if num_hit and date_hit:
        num_val, num_box, page_idx = num_hit
        date_val, date_box, _ = date_hit
        boxes = [b for b in (num_box, date_box) if b]
        bbox = [
            min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes),
        ] if boxes else None
        return f"{num_val} от {date_val}", bbox, page_idx
    return None


def _search_options(pages: List[OcrPage], options: List[str]):
    """Проход 1: точное вхождение. Короткие варианты («5», «4») сравниваются
    только с целыми токенами строки — иначе «5» матчится внутри дат.
    Проход 2: нечёткий — только для вариантов длиной >= 4 символов."""
    lowered = [o.lower() for o in options]
    for page in pages:
        for line in page.lines:
            low = line.text.lower()
            tokens = low.replace("(", " ").replace(")", " ").split()
            for opt_low in lowered:
                if len(opt_low) < 4:
                    if opt_low in tokens:
                        return opt_low, line.bbox, page.page_index
                elif opt_low in low:
                    return opt_low, line.bbox, page.page_index
    for page in pages:
        for line in page.lines:
            low = line.text.lower()
            for opt_low in lowered:
                if len(opt_low) >= 4 and (
                    int(fuzz.partial_ratio(opt_low, low)) >= settings.fuzz_threshold
                    # стем-совпадение: «очной» по стему «очн» матчит вариант «очная»
                    or (len(opt_low) >= 5 and opt_low[:-2] in low)
                ):
                    return opt_low, line.bbox, page.page_index
    return None


def _clean_anchor_tail(tail: str) -> str:
    """Чистка значения после якоря: краевые знаки и ведущие предлоги
    («в Федеральном...» → «Федеральном...»)."""
    tail = tail.lstrip(" \t:-—").strip()
    for prep in ("в ", "на ", "по "):
        if tail.lower().startswith(prep) and len(tail) > len(prep) + 2:
            tail = tail[len(prep):]
            break
    return _trailing_punct_re.sub("", tail).strip()


def _search_anchor_after(pages: List[OcrPage], anchors: List[str]):
    """Значение = текст после якорного слова до конца строки (или следующая
    строка). Якорь ищется с границей слова, чтобы не матчиться внутри
    «университете» по якорю «университет». Внешний цикл по якорям —
    приоритет сильного якоря из любой строки над слабым из первой."""
    for hit in anchors:
        for page in pages:
            lines = page.lines
            for i, line in enumerate(lines):
                low = line.text.lower()
                if hit.lower() not in low and \
                        int(fuzz.partial_ratio(hit.lower(), low)) < settings.fuzz_threshold:
                    continue
                m = re.search(re.escape(hit) + r"(?![а-яёa-z])", line.text, re.IGNORECASE)
                if m is None:
                    continue
                tail = _clean_anchor_tail(line.text[m.end():])
                if tail and len(tail) >= 2:
                    return _ws_re.sub(" ", tail), line.bbox, page.page_index
                if i + 1 < len(lines):  # значение перенесено на следующую строку
                    nxt = _clean_anchor_tail(lines[i + 1].text)
                    if nxt and (nxt[0].isupper() or nxt[0].isdigit()):
                        return _ws_re.sub(" ", nxt), lines[i + 1].bbox, page.page_index
    return None


def _detect_cv(pages: List[OcrPage], kind: str) -> str:
    """печать/подпись ищем по всем страницам; найдено хоть где-то → «есть»."""
    for page in pages:
        if kind == "stamp_and_sign":
            if detect_stamp(page.image) and detect_signature(page.image):
                return settings.yes_value
        elif kind == "signature_only":
            if detect_signature(page.image):
                return settings.yes_value
    return settings.no_value


# --- Публичный API ---

def extract_fields(doc_type: str, pages: List[OcrPage], registry: SchemaRegistry) -> List[FieldItem]:
    schema_fields = registry.fields(doc_type)
    result: List[FieldItem] = []

    for key, spec in schema_fields.items():
        ftype = spec.get("type", "regex")
        label = spec.get("label", key)
        value, bbox, page_idx, source = settings.not_found_value, None, 0, ftype

        if ftype == "cv_stamp_and_sign":
            value = _detect_cv(pages, "stamp_and_sign")
            source = "cv"
        elif ftype == "cv_signature_only":
            value = _detect_cv(pages, "signature_only")
            source = "cv"
        elif not pages or all(not p.lines for p in pages):
            pass  # OCR ничего не дал — «не найдено»
        elif ftype == "regex":
            # без IGNORECASE: классы [А-ЯЁ]/[а-яё] в схемах сами кодируют регистр
            pattern = re.compile(spec["regex"])
            found = _search_regex(pages, pattern, spec.get("join_groups", " "),
                                  take_last=spec.get("take_last", False))
            if not found and spec.get("regex_alt"):
                alt_pattern = re.compile(spec["regex_alt"])
                found = _search_regex(
                    pages, alt_pattern, spec.get("join_groups", " "),
                    take_last=spec.get("take_last", False),
                    swap_groups=spec.get("alt_swap_groups", False),
                )
            if not found and key == "doc_number_and_date":
                found = _fallback_number_and_date(pages)
            if found:
                value, bbox, page_idx = found
        elif ftype == "ner_person":
            pattern = re.compile(spec.get("regex", "")) if spec.get("regex") else None
            found = _search_regex(pages, pattern, " ") if pattern else None
            if found:
                value, bbox, page_idx = found
                source = "regex+ner"
            else:
                person = _ner_find_person("\n".join(p.text for p in pages))
                if person:
                    value, source = person, "ner_person"
                    # bbox — строка, где встретилось ФИО
                    for p in pages:
                        for line in p.lines:
                            if person.split()[0] in line.text or " ".join(person.split()[:2]) in line.text:
                                bbox, page_idx = line.bbox, p.page_index
                                break
        elif ftype == "options":
            found = _search_options(pages, spec.get("options", []))
            if found:
                value, bbox, page_idx = found
        elif ftype == "anchor_after":
            found = _search_anchor_after(pages, spec.get("anchors", []))
            if found:
                value, bbox, page_idx = found

        result.append(FieldItem(
            key=key, label=label, value=value,
            bbox=bbox, page=page_idx, source=source,
        ))

    return result
