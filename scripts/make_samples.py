"""Генерация синтетических сканов 3 типов документов + JSON-пар для batch_eval.

Варианты: полный документ, без печати, без части полей, повёрнутый на 12°.
Шрифты: C:/Windows/Fonts/arial.ttf (кириллица). Зависимости: только Pillow
+ NumPy (для «росчерка» подписи).

Запуск: python scripts/make_samples.py [--out backend/data/samples]
"""
import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DEFAULT = Path(__file__).resolve().parent.parent / "backend" / "data" / "samples"

W, H = 1240, 1754  # A4 @ 150 dpi
FONT_TITLE, FONT_BODY = 44, 30
INK = (25, 25, 25)
STAMP_COLOR = (30, 60, 160)  # RGB: сине-фиолетовые чернила печати


def _font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (r"C:\Windows\Fonts\arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                      "/usr/share/fonts/dejavu/DejaVuSans.ttf"):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    raise SystemExit("Не найден TTF-шрифт с кириллицей (arial.ttf / DejaVuSans.ttf)")


def _render(lines, title, stamp=False, signature=False):
    img = Image.new("RGB", (W, H), (250, 250, 248))
    draw = ImageDraw.Draw(img)
    y = 90
    if title:
        draw.text((W // 2 - len(title) * 12, y), title, font=_font(FONT_TITLE), fill=INK)
        y += 100
    for line in lines:
        draw.text((110, y), line, font=_font(FONT_BODY), fill=INK)
        y += 52

    if signature:  # плотный «росчерк» в правой нижней зоне
        rnd = random.Random(7)
        for stroke in range(6):
            x0 = 700 + stroke * 40
            pts = [(x0 + dx, int(1300 + 50 * math.sin(dx * 0.15 + stroke))) for dx in range(0, 220, 4)]
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                draw.line([(xa, ya + rnd.randint(-3, 3)), (xb, yb + rnd.randint(-3, 3))],
                          fill=INK, width=3)

    if stamp:  # круглая «гербовая печать»
        cx, cy, r = W - 260, H - 300, 120
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=STAMP_COLOR, width=7)
        draw.ellipse([cx - r + 14, cy - r + 14, cx + r - 14, cy + r - 14],
                     outline=STAMP_COLOR, width=3)
        draw.text((cx - 80, cy - 12), "ДЕКАНАТ", font=_font(24), fill=STAMP_COLOR)
    return img


def _save(img: Image.Image, name: str, out: Path, question: str, doc_type: str, samples: list):
    img.save(out / f"{name}.png")
    samples.append({"file_name": f"{name}.png", "question": question, "document_type": doc_type})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(OUT_DEFAULT))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    study_lines_full = [
        "Настоящая справка выдана Иванову Ивану Ивановичу в том, что он",
        "действительно обучается в Федеральном государственном университете",
        "по направлению подготовки 09.03.01 Информатика и вычислительная техника",
        "форма обучения: очная",
        "период обучения с 01.09.2023 по 30.06.2027",
        "№ 12/3-2024 от 10.09.2025",
    ]
    study_lines_no_university = [l for l in study_lines_full if "университете" not in l]

    leave_lines_full = [
        "от студента 3 курса группы ИВТ-31 Смирнова Алексея Сергеевича",
        "прошу предоставить академический отпуск по состоянию здоровья",
        "с 01.02.2026 по 31.01.2027",
        "дата подачи заявления: 15.01.2026",
    ]
    leave_lines_no_dates = [l for l in leave_lines_full if not l.startswith(("с ", "дата"))] \
        + ["дата подачи заявления: 15.01.2026"]

    internship_lines_full = [
        "Выдана студенту Иванову Ивану Ивановичу в том, что он проходил",
        "Организация: ООО «ТехноПром»",
        "сроки практики с 01.07.2025 по 31.08.2025",
        "Руководитель практики: Петров Пётр Петрович",
        "оценка: отлично",
        "№ 45/п-2025 от 05.09.2025",
    ]
    internship_lines_no_grade = [l for l in internship_lines_full if "оценка" not in l]

    samples = []

    # --- справка об обучении ---
    _save(_render(study_lines_full, "СПРАВКА ОБ ОБУЧЕНИИ", stamp=True, signature=True),
          "001_study_full", out, "Проверьте, всё ли в порядке с моей справкой об обучении",
          "study_certificate", samples)
    _save(_render(study_lines_full, "СПРАВКА ОБ ОБУЧЕНИИ", stamp=False, signature=True),
          "002_study_no_stamp", out, "Правильная ли моя справка об обучении?",
          "study_certificate", samples)
    _save(_render(study_lines_no_university, "СПРАВКА ОБ ОБУЧЕНИИ", stamp=True, signature=True),
          "003_study_no_university", out, "Можно ли принять эту справку об обучении?",
          "study_certificate", samples)
    rotated = _render(study_lines_full, "СПРАВКА ОБ ОБУЧЕНИИ", stamp=True, signature=True) \
        .rotate(12, resample=Image.BICUBIC, fillcolor=(250, 250, 248))
    _save(rotated, "004_study_rotated12", out, "Проверьте справку об обучении",
          "study_certificate", samples)

    # --- заявление на академический отпуск ---
    _save(_render(leave_lines_full, "ЗАЯВЛЕНИЕ", stamp=True, signature=True),
          "005_leave_full", out, "Хочу оформить академический отпуск, всё ли верно в заявлении?",
          "academic_leave_application", samples)
    _save(_render(leave_lines_no_dates, "ЗАЯВЛЕНИЕ", stamp=False, signature=False),
          "006_leave_no_dates", out, "Проверьте заявление на академический отпуск",
          "academic_leave_application", samples)

    # --- справка о практике ---
    _save(_render(internship_lines_full, "СПРАВКА О ПРАКТИКЕ", stamp=True, signature=True),
          "007_internship_full", out, "Проверьте справку о производственной практике",
          "internship_certificate", samples)
    _save(_render(internship_lines_no_grade, "СПРАВКА О ПРАКТИКЕ", stamp=True, signature=True),
          "008_internship_no_grade", out, "Годна ли моя справка о практике на предприятии?",
          "internship_certificate", samples)

    # --- вопрос вне Положения (демо ветки NO_INFO) ---
    _save(_render(study_lines_full, "СПРАВКА ОБ ОБУЧЕНИИ", stamp=True, signature=True),
          "009_study_offtopic", out, "Есть ли в общежитии свободные места на следующий год?",
          "study_certificate", samples)

    for sample in samples:
        stem = Path(sample["file_name"]).stem
        with open(out / f"{stem}.json", "w", encoding="utf-8") as f:
            json.dump(sample, f, ensure_ascii=False, indent=2)

    print(f"Сгенерировано {len(samples)} сканов и JSON-пар → {out}")


if __name__ == "__main__":
    main()
