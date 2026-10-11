"""Общие фикстуры: сборка OcrPage из текстовых строк без реального OCR."""
import numpy as np
import pytest

from app.core.ocr_engine import OcrLine, OcrPage


def make_page(lines, width=1600, height=2200, page_index=0):
    """lines — список (text, bbox) или просто строк текста (bbox генерируется)."""
    ocr_lines = []
    y = 100
    for item in lines:
        if isinstance(item, str):
            text, bbox = item, [80, y, 1200, y + 40]
            y += 60
        else:
            text, bbox = item
        ocr_lines.append(OcrLine(text=text, bbox=list(bbox), conf=0.95))
    return OcrPage(
        page_index=page_index,
        width=width,
        height=height,
        image=np.full((height, width, 3), 255, dtype=np.uint8),
        lines=ocr_lines,
    )


@pytest.fixture
def registry():
    from app.core.extractor import SchemaRegistry

    return SchemaRegistry()
