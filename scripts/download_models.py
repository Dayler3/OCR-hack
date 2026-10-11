"""Предскачивание моделей в локальный кэш, чтобы продовый запуск не тянул
сотни МБ из сети: PaddleOCR (det+rec для lang=ru) и rubert-tiny2.

Запуск: python scripts/download_models.py [--skip-embeddings]
"""
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")


def warm_paddle() -> bool:
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:
        print(f"[skip] PaddleOCR недоступен: {exc}")
        return False
    import numpy as np

    try:
        ocr = PaddleOCR(lang="ru", show_log=False)
    except TypeError:
        ocr = PaddleOCR(lang="ru", use_angle_cls=True, show_log=False)
    ocr.predict(np.full((64, 256, 3), 255, dtype=np.uint8)) if hasattr(ocr, "predict") \
        else ocr.ocr(np.full((64, 256, 3), 255, dtype=np.uint8), cls=True)
    print("[ok] PaddleOCR модели в кэше")
    return True


def warm_ner() -> bool:
    try:
        from natasha import Doc, NewsEmbedding, NewsNERTagger, Segmenter

        tagger = NewsNERTagger(NewsEmbedding())
        doc = Doc("Иванов Иван Иванович")
        doc.segment(Segmenter())
        doc.tag_ner(tagger)
        print("[ok] Natasha NER модели в кэше")
        return True
    except Exception as exc:
        print(f"[skip] Natasha недоступна: {exc}")
        return False


def warm_embeddings() -> bool:
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("cointegrated/rubert-tiny2")
        model.encode(["прогрев"])
        print("[ok] rubert-tiny2 в кэше")
        return True
    except Exception as exc:
        print(f"[skip] sentence-transformers недоступны: {exc}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-embeddings", action="store_true")
    args = parser.parse_args()
    warm_paddle()
    warm_ner()
    if not args.skip_embeddings:
        warm_embeddings()
    print("Готово.")
