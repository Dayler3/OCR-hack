"""Юнит-тесты извлечения полей по YAML-схемам (без OCR и CV)."""
from app.config import settings
from app.core.extractor import extract_fields
from app.core.classifier import classify_document
from tests.conftest import make_page


STUDY_CERT_TEXT = [
    "СПРАВКА ОБ ОБУЧЕНИИ",
    "Справка выдана Иванову Ивану Ивановичу в том, что он действительно обучается",
    "Университет: Федеральный государственный университет",
    "по направлению подготовки 09.03.01 Информатика и вычислительная техника",
    "форма обучения: очная",
    "период обучения с 01.09.2023 по 30.06.2027",
    "№ 12/3-2024 от 10.09.2025",
]


def _fields(pages, doc_type, registry):
    items = extract_fields(doc_type, pages, registry)
    return {f.key: f for f in items}


def test_study_certificate_full_extraction(registry):
    fields = _fields([make_page(STUDY_CERT_TEXT)], "study_certificate", registry)

    assert fields["fio"].value == "Иванову Ивану Ивановичу"
    assert fields["university"].value == "Федеральный государственный университет"
    assert "09.03.01" in fields["study_direction"].value
    assert fields["study_form"].value == "очная"
    assert fields["study_period"].value == "01.09.2023 по 30.06.2027"
    assert fields["doc_number_and_date"].value == "12/3-2024 от 10.09.2025"
    # bbox проставлен для regex-полей и лежит в пределах страницы
    assert fields["fio"].bbox == [80, 160, 1200, 200]


def test_missing_fields_become_not_found(registry):
    # нет ни направления, ни формы, ни номера
    poor_text = [
        "СПРАВКА",
        "выдана Петрову Петру Петровичу",
    ]
    fields = _fields([make_page(poor_text)], "study_certificate", registry)
    assert fields["study_direction"].value == settings.not_found_value
    assert fields["study_form"].value == settings.not_found_value
    assert fields["study_period"].value == settings.not_found_value
    assert fields["doc_number_and_date"].value == settings.not_found_value
    assert fields["fio"].value == "Петрову Петру Петровичу"


def test_academic_leave_dates(registry):
    text = [
        "Декану факультета",
        "ЗАЯВЛЕНИЕ",
        "от студента 3 курса группы ИВТ-31 Смирнова Алексея Сергеевича",
        "прошу предоставить академический отпуск по состоянию здоровья",
        "с 01.02.2026 по 31.01.2027",
        "дата подачи заявления: 15.01.2026",
    ]
    fields = _fields([make_page(text)], "academic_leave_application", registry)
    assert fields["start_date"].value == "01.02.2026"
    assert fields["end_date"].value == "31.01.2027"
    assert fields["application_date"].value == "15.01.2026"
    assert "Смирнова Алексея Сергеевича" == fields["fio"].value
    assert "групп" in text[2].lower()


def test_options_fuzzy_match(registry):
    # «оч­ной» с опечаткой/падежом должна нечётко сматчиться на «очная»
    text = ["форма обучения очной"]
    fields = _fields([make_page(text)], "study_certificate", registry)
    assert fields["study_form"].value == "очная"


def test_anchor_after_word_boundary(registry):
    # якорь «университет» не должен матчиться внутри слова «университете»
    text = ["обучается в Федеральном государственном университете"]
    fields = _fields([make_page(text)], "study_certificate", registry)
    assert fields["university"].value != "ете"
    assert fields["university"].value == settings.not_found_value or \
        "университет" in fields["university"].value.lower()


def test_classifier_detects_type(registry):
    page = make_page(STUDY_CERT_TEXT)
    doc_type, confidence = classify_document([page], registry)
    assert doc_type == "study_certificate"
    assert confidence > 0


def test_classifier_real_world_spravka(registry):
    """Реальный бланк (МЭИ, 2017): ни один фразовый якорь не совпадает,
    тип должен определиться по стем-ключевым словам."""
    text = [
        "МИНИСТЕРСТВО ОБРАЗОВАНИЯ И НАУКИ РОССИЙСКОЙ ФЕДЕРАЦИИ",
        "Федеральное государственное бюджетное образовательное учреждение",
        "высшего образования «Национальный исследовательский университет «МЭИ»",
        "СПРАВКА",
        "Дана Гурову Александру Сергеевичу в том, что он является студентом",
        "дневного отделения и обучается на первом курсе факультета",
        "«Информационные технологии в энергетике»",
        "Приказ о зачислении № 5788/у от 04.08.2014 г.",
        "Выдана для предъявления по месту требования.",
    ]
    doc_type, confidence = classify_document([make_page(text)], registry)
    assert doc_type == "study_certificate"
    assert confidence >= 0.3


def test_classifier_no_match(registry):
    page = make_page(["привет мир", "как дела"])
    doc_type, confidence = classify_document([page], registry)
    assert doc_type is None


def test_realistic_mei_style_extraction(registry):
    """Реальный бланк: заглавные первые буквы («Период…», «Дана…»),
    приказ о зачислении № раньше номера справки."""
    text = [
        "МИНИСТЕРСТВО ОБРАЗОВАНИЯ И НАУКИ РОССИЙСКОЙ ФЕДЕРАЦИИ",
        "высшего образования «Национальный исследовательский университет «Мэи»",
        "СПРАВКА",
        "Дана Гурову Александру Сергеевичу в том, что он является студентом",
        "дневного отделения и обучается на первом курсе факультета",
        "Период обучения с 01.09.2014 по 30.06.2018.",
        "Приказ о зачислении № 5788/у от 04.08.2014 г.",
        "Справка № 273-ф от 30.06.2016 г.",
    ]
    fields = _fields([make_page(text)], "study_certificate", registry)
    assert fields["fio"].value == "Гурову Александру Сергеевичу"
    assert fields["study_period"].value == "01.09.2014 по 30.06.2018"
    # берём последний № — номер справки, а не приказа о зачислении
    assert fields["doc_number_and_date"].value == "273-ф от 30.06.2016"


def test_new_doc_type_via_yaml_only(tmp_path, registry):
    """Бонус-требование: новый тип добавляется в YAML без правок кода."""
    import yaml

    with open(registry.path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["documents"]["reference_certificate"] = {
        "name": "Справка с места жительства",
        "anchors": ["справка с места жительства"],
        "fields": {
            "fio": {"label": "ФИО", "type": "regex", "regex": "выдана\\s+([А-ЯЁ][а-яё]+)"},
        },
    }
    tmp = tmp_path / "extended.yaml"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)

    from app.core.extractor import SchemaRegistry
    extended = SchemaRegistry(tmp)
    fields = _fields(
        [make_page(["СПРАВКА С МЕСТА ЖИТЕЛЬСТВА", "выдана Кузнецову"])],
        "reference_certificate", extended,
    )
    assert fields["fio"].value == "Кузнецову"


def test_classifier_with_question_and_mws_bench_doc(registry):
    """Автоклассификация документа из MWS-Vision-Bench при вопросе «Могу ли я перевестись?»."""
    from app.core.classifier import classify_document

    mws_lines = [
        "ГЛАВНЫЙ ГОСУДАРСТВЕННЫЙ САНИТАРНЫЙ ВРАЧ РОССИЙСКОЙ ФЕДЕРАЦИИ",
        "ПОСТАНОВЛЕНИЕ",
        "14.02.2025",
        "г. Москва",
        "№ 2",
        "О внесении изменений в санитарные правила СП 2.1.3678-20",
    ]
    pages = [make_page(mws_lines)]
    doc_type, conf = classify_document(pages, registry, question="Могу ли я перевестись?")
    assert doc_type == "study_certificate"
    assert conf > 0.0

    fields = _fields(pages, doc_type, registry)
    assert fields["doc_number_and_date"].value == "2 от 14.02.2025"
    assert fields["fio"].value == "не найдено"

