"""Пакетная оценка: прогон пайплайна по тестовому набору и генерация
results.json для закрытой проверки жюри (§10 ТЗ).

Поддерживаемые форматы входного каталога:
  1. metadata.jsonl (экспорт MTSAIR/MWS-Vision-Bench из scripts/download_dataset.py):
     строки {"file_name": ..., "question": ..., "type": ..., "dataset_name": ..., "answers": [...]}
  2. Каталог *.json-пар {"file_name": ..., "question": ...} (классический формат ТЗ)

Структура выходных записей — по mock-образцу §10 ТЗ (верифицировать по README
организаторов при закрытой проверке):
  {file_name, question, document_type, extracted_fields, answer, rule_source}

Запуск:
  python batch_eval.py --input-dir data/samples --output results.json
  python batch_eval.py --input-dir data/mws_bench --metadata metadata.jsonl --output results.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.pipeline import ProcessPipeline  # noqa: E402


def iter_entries(input_dir: Path):
    """→ (file_name, question, doc_type_hint) по metadata.jsonl или *.json-парам."""
    meta_path = None
    for candidate in ("metadata.jsonl", "metadata.json"):
        if (input_dir / candidate).exists():
            meta_path = input_dir / candidate
            break

    if meta_path is not None:
        text = meta_path.read_text(encoding="utf-8").strip()
        rows = json.loads(text) if meta_path.suffix == ".json" else [
            json.loads(line) for line in text.splitlines() if line.strip()
        ]
        for row in rows:
            yield row.get("file_name", ""), row.get("question", ""), None
        return

    for sample in sorted(input_dir.glob("*.json")):
        with open(sample, "r", encoding="utf-8") as f:
            meta = json.load(f)
        yield meta.get("file_name", ""), meta.get("question", ""), meta.get("document_type")


def run_evaluation(input_dir: str, output_path: str, with_images: bool = False) -> None:
    input_path = Path(input_dir)
    pipeline = ProcessPipeline(include_page_images=with_images)

    results, errors = [], []
    processed = 0
    for file_name, question, doc_type in iter_entries(input_path):
        doc_path = input_path / file_name
        if not doc_path.exists():
            errors.append(f"файл не найден: {file_name}")
            continue
        try:
            response = pipeline.run(doc_path, question=question, doc_type=doc_type)
        except Exception as exc:  # одна битая пара не должна ронять весь прогон
            errors.append(f"{file_name}: {exc}")
            continue

        results.append({
            "file_name": file_name,
            "question": question,
            "document_type": response.document_type or "не определён",
            "extracted_fields": {f.key: f.value for f in response.fields},
            "answer": response.verdict.text,
            "rule_source": response.verdict.rule_source,
            "status": response.verdict.status,
        })
        processed += 1
        print(f"[{processed}] {file_name}: {response.verdict.status} "
              f"({response.document_type or '—'})", flush=True)

    with open(output_path, "w", encoding="utf-8") as out:
        json.dump(results, out, ensure_ascii=False, indent=2)

    print(f"\nГотово: {processed} записей → {output_path}")
    if errors:
        print(f"Ошибки ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Пакетная оценка и генерация results.json")
    parser.add_argument("--input-dir", type=str, required=True,
                        help="каталог с файлами + metadata.jsonl или *.json-парами")
    parser.add_argument("--output", type=str, default="results.json")
    parser.add_argument("--with-images", action="store_true",
                        help="включить base64-страницы в ответ (медленнее, только для отладки)")
    args = parser.parse_args()
    run_evaluation(args.input_dir, args.output, args.with_images)
