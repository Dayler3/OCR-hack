"""Тесты препроцессинга: deskew до 30°, апскейл, CLAHE."""
import cv2
import numpy as np

from app.core.preprocessor import deskew_and_enhance


def _page_with_lines(width=900, height=700):
    """Белый лист с чёрными «строками текста» — горизонтальные прямоугольники."""
    img = np.full((height, width, 3), 255, dtype=np.uint8)
    for y in range(80, height - 60, 70):
        cv2.rectangle(img, (100, y), (width - 100, y + 14), (0, 0, 0), -1)
    return img


def _rotate(image, angle):
    h, w = image.shape[:2]
    mat = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(image, mat, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def test_deskew_compensates_tilt():
    for tilt in (5.0, 15.0, 28.0):
        rotated = _rotate(_page_with_lines(), tilt)
        result = deskew_and_enhance(rotated)
        # детектированный угол должен компенсировать наклон (±3° допуск)
        assert abs(result.angle + tilt) < 3.0, f"наклон {tilt}°, детектировано {result.angle}°"


def test_straight_page_untouched():
    result = deskew_and_enhance(_page_with_lines())
    assert abs(result.angle) < 3.0


def test_lowres_upscale():
    small = _page_with_lines(width=400, height=300)
    result = deskew_and_enhance(small)
    assert min(result.image.shape[:2]) >= 1200
    assert result.scale > 1.0


def test_grayscale_and_rgba_input():
    gray = cv2.cvtColor(_page_with_lines(), cv2.COLOR_BGR2GRAY)
    assert deskew_and_enhance(gray).image.ndim == 3
    bgra = cv2.cvtColor(_page_with_lines(), cv2.COLOR_BGR2BGRA)
    assert deskew_and_enhance(bgra).image.shape[2] == 3
