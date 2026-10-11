"""Загрузка выборки бенчмарка MTSAIR/MWS-Vision-Bench с Hugging Face.

Сохраняет изображения + metadata.jsonl в backend/data/mws_bench/ — формат,
который читает batch_eval.py:
    {"file_name": ..., "question": ..., "type": ..., "dataset_name": ..., "answers": [...]}

Требует: pip install datasets (см. requirements-ml.txt).

Запуск:
    python scripts/download_dataset.py --limit 50
    python scripts/download_dataset.py --types "key information extraction ru" --limit 100
"""
import argparse
import json
from pathlib import Path

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "backend" / "data" / "mws_bench"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="MTSAIR/MWS-Vision-Bench")
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=50, help="максимум строк (0 = все)")
    parser.add_argument("--types", default="", help="фильтр по колонке type, через запятую")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    try:
        from datasets import load_dataset
    except ImportError:
        raise SystemExit("Нужна библиотека datasets: pip install -r backend/requirements-ml.txt")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    wanted_types = {t.strip().lower() for t in args.types.split(",") if t.strip()}
    ds = load_dataset(args.dataset, split=args.split)

    meta_rows, saved = [], 0
    for row in ds:
        if wanted_types and row.get("type", "").lower() not in wanted_types:
            continue
        if args.limit and saved >= args.limit:
            break

        image = row.get("image")
        if image is None:
            continue
        file_name = f"{row.get('id', saved):04d}.jpg"
        image.convert("RGB").save(out_dir / file_name, quality=92)

        meta_rows.append({
            "file_name": file_name,
            "question": row.get("question", ""),
            "type": row.get("type", ""),
            "dataset_name": row.get("dataset_name", ""),
            "answers": row.get("answers", []),
        })
        saved += 1

    with open(out_dir / "metadata.jsonl", "w", encoding="utf-8") as f:
        for row in meta_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Сохранено {saved} изображений и metadata.jsonl → {out_dir}")


if __name__ == "__main__":
    main()
