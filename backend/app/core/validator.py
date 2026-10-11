"""Детерминированный Rule Engine: проверка обязательных полей по пункту
Положения и генерация ответа строго по шаблонам §4 ТЗ (без галлюцинаций)."""
from typing import Dict, Optional

from app.config import settings
from app.core.rag_engine import Rule
from app.schemas.models import FieldItem, Verdict


def evaluate_document_rules(
    doc_name: str,
    fields: Dict[str, FieldItem],
    rule: Rule,
) -> Verdict:
    """Ветки OK / MISSING_FIELDS. NO_INFO формируется в pipeline (когда
    RAG не нашёл пункта Положения по вопросу)."""
    missing = []
    for field_key in rule.mandatory_fields:
        item = fields.get(field_key)
        if item is None:
            continue
        if not item.value or item.value in (settings.not_found_value, settings.no_value):
            missing.append(item.label)

    if not missing:
        return Verdict(
            status="OK",
            text=(f"{doc_name} содержит все данные, которые требует {rule.rule_id}. "
                  f"Окончательное решение примет сотрудник деканата."),
            rule_source=rule.rule_id,
        )
    missing_str = ", ".join(missing)
    return Verdict(
        status="MISSING_FIELDS",
        text=f"Не хватает: {missing_str}. Эти поля обязательны по {rule.rule_id}.",
        rule_source=rule.rule_id,
    )


def no_info_verdict(question: Optional[str]) -> Verdict:
    """Шаблон «Ответа нет»: «В документе и в Положении нет информации о {тема
    вопроса}. Обратитесь в деканат». Если вопрос не задан, тема не известна."""
    topic = (question or "").strip().rstrip("?.! ")
    if not topic:
        topic = "запрошенной теме"
    return Verdict(
        status="NO_INFO",
        text=f"В документе и в Положении нет информации о {topic}. Обратитесь в деканат.",
        rule_source=None,
    )
