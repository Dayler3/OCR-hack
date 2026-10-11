# Бэкенд: Цифровой секретарь онлайн-деканата (CPU-only, без внешних LLM-API)
FROM python:3.11-slim

WORKDIR /srv

# libglib/libgl — рантайм-зависимости OpenCV; libgomp — paddle
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-ml.txt

COPY app ./app
COPY configs ./configs
COPY data ./data
COPY batch_eval.py ./

# Предскачивание моделей PaddleOCR в слой образа (прогрев на пустой картинке)
RUN python - <<'PY'
import numpy as np
try:
    from paddleocr import PaddleOCR
    try:
        ocr = PaddleOCR(lang="ru", show_log=False)
    except TypeError:
        ocr = PaddleOCR(lang="ru", use_angle_cls=True, show_log=False)
    img = np.full((64, 256, 3), 255, dtype=np.uint8)
    ocr.predict(img) if hasattr(ocr, "predict") else ocr.ocr(img, cls=True)
    print("paddle models cached")
except Exception as exc:
    print("warmup skipped:", exc)
PY

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
