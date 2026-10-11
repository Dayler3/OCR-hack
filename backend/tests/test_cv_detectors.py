"""Тесты CV-детекторов печати/подписи на синтетических изображениях."""
import cv2
import numpy as np

from app.core.cv_detectors import detect_signature, detect_stamp


def _white(w=800, h=1100):
    return np.full((h, w, 3), 255, dtype=np.uint8)


def test_detect_stamp_blue_circle():
    img = _white()
    # круглая синяя «печать» в нижней трети
    cv2.circle(img, (400, 900), 90, (255, 100, 60), -1)  # BGR: синие чернила
    assert detect_stamp(img) is True


def test_no_stamp_on_clean_page():
    assert detect_stamp(_white()) is False


def test_no_stamp_on_black_rectangle():
    img = _white()
    cv2.rectangle(img, (300, 850), (500, 950), (0, 0, 0), -1)  # не круглая форма
    assert detect_stamp(img) is False


def _draw_signature(img):
    """Плотный «росчерк» в правом нижнем углу, как рукописная подпись."""
    rng = np.random.default_rng(42)
    for stroke in range(6):
        x0 = 480 + stroke * 40
        pts = [(x0 + int(dx), 950 + int(60 * np.sin(dx * 0.15 + stroke)))
               for dx in range(0, 220, 4)]
        pts = [(x, min(y, 1080)) for x, y in pts]
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            jitter = int(rng.integers(-3, 4))
            cv2.line(img, (xa, ya + jitter), (xb, yb + jitter), (30, 30, 30), 3)
    return img


def test_detect_signature_squiggle():
    img = _draw_signature(_white())
    assert detect_signature(img) is True


def test_no_signature_on_clean_page():
    assert detect_signature(_white()) is False


def test_signature_respects_bbox():
    img = _draw_signature(_white())
    # пустая целевая зона — подпись вне bbox не засчитывается
    assert detect_signature(img, signature_bbox=[0, 0, 100, 100]) is False
