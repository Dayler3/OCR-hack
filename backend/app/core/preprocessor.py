"""Препроцессинг сканов: компенсация наклона до 30°, нормализация освещения
(CLAHE), адаптивный апскейл при низком разрешении. Основа — §8.2 ТЗ.

Контракт: bbox всех последующих этапов (OCR, подсветка на фронте) живут
в координатах ИЗОБРАЖЕНИЯ, возвращаемого этим модулем (PLAN.md §3).
"""
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

MIN_SIDE_TARGET = 1200  # целевая меньшая сторона при апскейле
UNEVENNESS_THRESHOLD = 15.0  # разброс яркости фона по сетке 8x8, выше — есть тени/блики


def _needs_illumination_fix(image: np.ndarray) -> bool:
    """CLAHE нужен только при неравномерном освещении: на чистом скане он
    амплифицирует шум и детектор текста теряет строки.

    Яркость фона оцениваем через морфологическое закрытие крупным ядром —
    оно стирает тёмные штрихи текста (иначе жирный заголовок в ячейке сетки
    выглядит как «тень»)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 51))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    means = cv2.resize(background, (8, 8), interpolation=cv2.INTER_AREA)
    return float(means.max()) - float(means.min()) > UNEVENNESS_THRESHOLD


@dataclass
class PreprocessResult:
    image: np.ndarray          # BGR после всех преобразований
    angle: float               # применённый угол поворота (градусы)
    scale: float               # применённый коэффициент апскейла


def _to_bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def _estimate_angle(gray: np.ndarray) -> float:
    """Медианный угол почти-горизонтальных линий (HoughLinesP)."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=20)
    if lines is None:
        return 0.0
    angles: List[float] = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        deg = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
        if -35.0 <= deg <= 35.0 and abs(deg) > 0.5:
            angles.append(deg)
    return float(np.median(angles)) if angles else 0.0


def deskew_and_enhance(image: np.ndarray) -> PreprocessResult:
    image = _to_bgr(np.ascontiguousarray(image))
    h, w = image.shape[:2]

    # 1. Адаптивный апскейл при низком разрешении
    scale = 1.0
    if min(h, w) < MIN_SIDE_TARGET:
        scale = MIN_SIDE_TARGET / min(h, w)
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)
        h, w = image.shape[:2]

    # 2. Определение и компенсация наклона (до ±30°)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    angle = _estimate_angle(gray)
    if abs(angle) > 0.5:
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        image = cv2.warpAffine(
            image, rot_mat, (w, h),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
        )

    # 3. Нормализация освещения: CLAHE по каналу L в LAB — только при
    # неравномерном освещении (тени/блики); чистые сканы не трогаем
    if _needs_illumination_fix(image):
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b_ch = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab = cv2.merge((clahe.apply(l), a, b_ch))
        image = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    return PreprocessResult(image=image, angle=angle, scale=scale)
