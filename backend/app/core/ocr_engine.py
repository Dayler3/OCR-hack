"""OCR-движок: PaddleOCR (основной, PP-OCRv4/v5, lang=ru) с фолбэком на
pytesseract. Ленивая инициализация — модуль импортируется без тяжёлых
зависимостей (тесты, /api/schemas).

Возвращает строки текста с bbox в координатах поданного изображения —
это же изображение уходит на фронт как подложка подсветки (PLAN.md §3).
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class OcrLine:
    text: str
    bbox: List[int]  # [x1, y1, x2, y2]
    conf: float


# OCR на кириллице регулярно выдаёт латинские омоглифы («oт», «c» вместо «с»).
# Для русских документов безопаснее унифицировать их в кириллицу.
_LATIN_TO_CYRILLIC = str.maketrans({
    "a": "а", "c": "с", "e": "е", "o": "о", "p": "р", "x": "х", "y": "у", "n": "п",
    "A": "А", "C": "С", "E": "Е", "O": "О", "P": "Р", "X": "Х", "Y": "У",
    "B": "В", "H": "Н", "K": "К", "M": "М", "T": "Т",
})


def normalize_text(text: str) -> str:
    return text.translate(_LATIN_TO_CYRILLIC)


@dataclass
class OcrPage:
    page_index: int
    width: int
    height: int
    image: np.ndarray  # препроцесснутое изображение (нужно cv-детекторам)
    lines: List[OcrLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


class OcrError(RuntimeError):
    pass


def _points_to_bbox(points) -> List[int]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


class OcrEngine:
    """Обёртка над PaddleOCR/pytesseract с единым интерфейсом."""

    def __init__(self, engine: Optional[str] = None):
        self._requested = engine or settings.ocr_engine
        self._paddle = None
        self._engine_name: Optional[str] = None

    @property
    def engine_name(self) -> Optional[str]:
        return self._engine_name

    # --- инициализация движков (лениво, при первом recognize) ---

    def _init_paddle(self):
        try:
            from paddleocr import PaddleOCR
        except Exception as exc:  # ImportError или битые зависимости
            logger.info("PaddleOCR недоступен: %s", exc)
            return None
        # API менялся между версиями: пробуем сигнатуры от новой к старой.
        # enable_mkldnn=False — обход OneDNN-бага paddlepaddle 3.3.x на Windows CPU
        mkldnn = settings.ocr_enable_mkldnn
        signatures = (
            lambda: PaddleOCR(
                lang=settings.ocr_lang,
                device="cpu",
                enable_mkldnn=mkldnn,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            ),
            lambda: PaddleOCR(lang=settings.ocr_lang, device="cpu", enable_mkldnn=mkldnn),
            lambda: PaddleOCR(lang=settings.ocr_lang),
            lambda: PaddleOCR(lang=settings.ocr_lang, use_angle_cls=True, show_log=False),  # 2.x
        )
        for make in signatures:
            try:
                return make()
            except TypeError:
                continue
            except Exception as exc:
                logger.warning("PaddleOCR не инициализировался: %s", exc)
                return None
        return None

    def _init_tesseract(self):
        try:
            import pytesseract  # noqa: F401
            import shutil
            if shutil.which("tesseract") is None:
                return None
            return "tesseract"
        except Exception:
            return None

    def _ensure_engine(self) -> str:
        if self._engine_name:
            return self._engine_name
        order = (
            ["paddle", "tesseract"]
            if self._requested in ("auto", "paddle")
            else ["tesseract", "paddle"]
            if self._requested == "tesseract"
            else [self._requested]
        )
        for name in order:
            if name == "paddle":
                self._paddle = self._init_paddle()
                if self._paddle is not None:
                    self._engine_name = "paddle"
                    return self._engine_name
            elif name == "tesseract":
                if self._init_tesseract():
                    self._engine_name = "tesseract"
                    return self._engine_name
        raise OcrError(
            "OCR-движок недоступен. Установите PaddleOCR: pip install -r requirements-ml.txt "
            "(или системный tesseract + pip install pytesseract)."
        )

    # --- распознавание ---

    def _recognize_paddle(self, image: np.ndarray) -> List[OcrLine]:
        try:
            result = self._paddle.predict(image)  # paddleocr >= 3.x
        except AttributeError:
            result = self._paddle.ocr(image, cls=True)  # 2.x
        lines: List[OcrLine] = []
        for page in result or []:
            # 3.x: OCRResult.json = {'res': {rec_texts, rec_boxes, rec_scores, ...}}
            payload = getattr(page, "json", None)
            if isinstance(payload, dict):
                payload = payload.get("res", payload)
            if isinstance(payload, dict) and "rec_texts" in payload:
                for text, box, conf in zip(
                    payload["rec_texts"], payload["rec_boxes"],
                    payload.get("rec_scores", [1.0] * len(payload["rec_texts"])),
                ):
                    if not text:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in box]
                    lines.append(OcrLine(normalize_text(text), [x1, y1, x2, y2], float(conf)))
            elif page:  # 2.x: [[points, (text, conf)], ...]
                for item in page:
                    points, (text, conf) = item[0], item[1]
                    if not text:
                        continue
                    lines.append(OcrLine(normalize_text(text), _points_to_bbox(points), float(conf)))
        return lines

    def _recognize_tesseract(self, page: OcrPage) -> List[OcrLine]:
        import cv2
        import pytesseract
        data = pytesseract.image_to_data(
            cv2.cvtColor(page.image, cv2.COLOR_BGR2RGB),
            lang="rus", output_type=pytesseract.Output.DICT,
        )
        lines: List[OcrLine] = []
        current_words: List[tuple] = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if not text or int(data["conf"][i]) < 0:
                continue
            word = (
                text,
                [data["left"][i], data["top"][i],
                 data["left"][i] + data["width"][i], data["top"][i] + data["height"][i]],
                float(data["conf"][i]) / 100.0,
            )
            # склеиваем слова одной строки по (block, par, line)
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            if current_words and current_words[-1][0] == key:
                current_words[-1][1].append(word)
            else:
                current_words.append((key, [word]))
        for _, words in current_words:
            text = " ".join(w[0] for w in words)
            xs1 = min(w[1][0] for w in words); ys1 = min(w[1][1] for w in words)
            xs2 = max(w[1][2] for w in words); ys2 = max(w[1][3] for w in words)
            lines.append(OcrLine(text, [xs1, ys1, xs2, ys2],
                                 max(w[2] for w in words)))
        return lines

    def recognize_page(self, page: OcrPage) -> OcrPage:
        engine = self._ensure_engine()
        page.lines = (
            self._recognize_paddle(page.image)
            if engine == "paddle"
            else self._recognize_tesseract(page)
        )
        return page


# --- загрузка документов ---

def load_document_pages(file_path: str | Path) -> List[np.ndarray]:
    """JPG/PNG/PDF (в т.ч. многостраничный) → список BGR-изображений."""
    import cv2
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        import fitz  # PyMuPDF
        pages = []
        with fitz.open(path) as doc:
            for num, pdf_page in enumerate(doc):
                if num >= settings.max_pages:
                    break
                pix = pdf_page.get_pixmap(dpi=settings.pdf_dpi)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                pages.append(cv2.cvtColor(img, cv2.COLOR_RGB2BGR) if pix.n >= 3 else img)
        if not pages:
            raise OcrError(f"PDF без страниц: {path}")
        return pages

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise OcrError(f"Не удалось прочитать изображение: {path}")
    return [image]
