"""Тесты трёх веток вердикта (§4 ТЗ) и RAG-поиска пункта Положения."""
from app.core.rag_engine import RagEngine
from app.core.validator import evaluate_document_rules, no_info_verdict
from app.schemas.models import FieldItem


def _fields(values: dict, doc_type="study_certificate") -> dict:
    return {
        key: FieldItem(key=key, label=RULE_LABELS.get(key, key), value=value)
        for key, value in values.items()
    }


RULE_LABELS = {
    "fio": "ФИО студента", "university": "Название вуза",
    "study_direction": "Направление подготовки", "study_form": "Форма обучения",
    "study_period": "Период обучения", "doc_number_and_date": "Номер и дата выдачи",
    "stamp_and_signature": "Подпись и печать",
}


def test_verdict_ok():
    rag = RagEngine()
    rule = rag.retrieve("нужна справка об обучении, всё ли в порядке с документом?",
                        doc_type="study_certificate")
    assert rule is not None and rule.rule_id == "п. 3.1 Положения"

    full = _fields({
        "fio": "Иванов Иван", "university": "МГУ", "study_direction": "Информатика",
        "study_form": "очная", "study_period": "2023–2027",
        "doc_number_and_date": "№1 от 01.01.2025", "stamp_and_signature": "есть",
    })
    verdict = evaluate_document_rules("Справка об обучении", full, rule)
    assert verdict.status == "OK"
    assert "содержит все данные" in verdict.text
    assert "п. 3.1 Положения" in verdict.text
    assert verdict.rule_source == rule.rule_id


def test_verdict_missing_fields():
    rag = RagEngine()
    rule = rag.retrieve("проверьте справку об обучении", doc_type="study_certificate")
    assert rule is not None

    incomplete = _fields({
        "fio": "Иванов Иван",
        "university": "не найдено",
        "study_direction": "не найдено",
        "study_form": "очная", "study_period": "2023–2027",
        "doc_number_and_date": "№1 от 01.01.2025",
        "stamp_and_signature": "нет",
    })
    verdict = evaluate_document_rules("Справка об обучении", incomplete, rule)
    assert verdict.status == "MISSING_FIELDS"
    assert "Название вуза" in verdict.text and "Направление подготовки" in verdict.text
    assert "Подпись и печать" in verdict.text  # «нет» тоже считается отсутствием
    assert "п. 3.1 Положения" in verdict.text


def test_verdict_no_info_when_question_outside_regulations():
    rag = RagEngine()
    rule = rag.retrieve("какая погода будет завтра в деканате?")
    assert rule is None

    verdict = no_info_verdict("какая погода будет завтра в деканате?")
    assert verdict.status == "NO_INFO"
    assert verdict.text.startswith("В документе и в Положении нет информации о ")
    assert verdict.text.endswith("Обратитесь в деканат.")
    assert verdict.rule_source is None


def test_rag_prefers_rule_of_document_type():
    rag = RagEngine()
    rule = rag.retrieve("проверьте мой документ", doc_type="internship_certificate")
    assert rule is not None
    assert rule.rule_id == "п. 3.3 Положения"


def test_no_info_verdict_empty_question():
    verdict = no_info_verdict("")
    assert verdict.status == "NO_INFO"
    assert "запрошенной теме" in verdict.text


def test_rag_transfer_question():
    rag = RagEngine()
    rule = rag.retrieve("Могу ли я перевестись?", doc_type="study_certificate")
    assert rule is not None
    assert rule.rule_id == "п. 3.1 Положения"

