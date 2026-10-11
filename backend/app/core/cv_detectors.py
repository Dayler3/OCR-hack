"""CV-детекция гербовой печати (HSV + круглость) и рукописной подписи
(плотность рёбер). Основа — §8.3 ТЗ, пороги вынесены для калибровки."""
import cv2
import numpy as np

# Пороги калибруются на синтетике (scripts/make_samples.py)
STAMP_MIN_AREA = 800          # мин. площадь контура печати, px²
STAMP_MIN_CIRCULARITY = 0.25  # круглость = 4πA/P²
SIGNATURE_MIN_DENSITY = 0.015  # мин. плотность рёбер в ROI подписи


def detect_stamp(image: np.ndarray) -> bool:
    """Детекция синей/фиолетовой гербовой печати в нижней половине документа."""
    h = image.shape[0]
    bottom_half = image[int(h * 0.45):, :]
    hsv = cv2.cvtColor(bottom_half, cv2.COLOR_BGR2HSV)

    blue_mask = cv2.inRange(hsv, np.array([95, 50, 50]), np.array([130, 255, 255]))
    violet_mask = cv2.inRange(hsv, np.array([130, 50, 50]), np.array([160, 255, 255]))
    mask = cv2.bitwise_or(blue_mask, violet_mask)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > STAMP_MIN_AREA:
            perimeter = cv2.arcLength(cnt, True)
            if perimeter > 0:
                circularity = 4 * np.pi * (area / (perimeter * perimeter))
                if circularity > STAMP_MIN_CIRCULARITY:
                    return True
    return False


def detect_signature(image: np.ndarray, signature_bbox=None) -> bool:
    """Анализ плотности штрихов рукописной подписи в целевой зоне."""
    if signature_bbox:
        x1, y1, x2, y2 = signature_bbox
        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return False
    else:
        h, w = image.shape[:2]
        roi = image[int(h * 0.7):, int(w * 0.4):]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 120)
    density = float(np.sum(edges > 0)) / (edges.shape[0] * edges.shape[1])
    return density > SIGNATURE_MIN_DENSITY
