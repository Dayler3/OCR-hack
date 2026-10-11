"""Тесты REST API (TestClient) с подменой пайплайна — без OCR-моделей."""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import routes
from app.schemas.models import AnalyzeResponse, FieldItem, PageInfo, Verdict

client = TestClient(app)


class MockPipeline:
    def run(self, file_path, question, doc_type=None):
        return AnalyzeResponse(
            document_type="study_certificate",
            document_name="Справка об обучении",
            classifier_confidence=0.75,
            pages=[PageInfo(width=100, height=50, image_b64="aGk=")],
            fields=[FieldItem(key="fio", label="ФИО студента",
                              value="Иванов Иван Иванович", bbox=[1, 2, 3, 4], page=0)],
            verdict=Verdict(status="OK", text="...", rule_source="п. 3.1 Положения"),
            timings_ms={"preprocess_ocr": 1},
        )


@pytest.fixture(autouse=True)
def mock_pipeline():
    routes.set_pipeline(MockPipeline())
    yield
    routes.set_pipeline(None)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["schemas_loaded"] == 3


def test_schemas_list():
    r = client.get("/api/schemas")
    assert r.status_code == 200
    schemas = r.json()
    assert {s["key"] for s in schemas} == {
        "study_certificate", "academic_leave_application", "internship_certificate"}
    by_key = {s["key"]: s for s in schemas}
    assert by_key["study_certificate"]["name"] == "Справка об обучении"
    assert len(by_key["study_certificate"]["fields"]) == 7


def test_analyze_png():
    import cv2
    import numpy as np

    ok, buf = cv2.imencode(".png", np.zeros((60, 80, 3), dtype=np.uint8))
    r = client.post(
        "/api/analyze",
        files={"file": ("doc.png", io.BytesIO(buf.tobytes()), "image/png")},
        data={"question": "проверьте справку", "doc_type": "study_certificate"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["document_type"] == "study_certificate"
    assert body["fields"][0]["key"] == "fio"
    assert body["verdict"]["status"] == "OK"
    assert body["pages"][0]["image_b64"]


def test_analyze_rejects_bad_format():
    r = client.post(
        "/api/analyze",
        files={"file": ("doc.gif", io.BytesIO(b"gif"), "image/gif")},
        data={"question": "?"},
    )
    assert r.status_code == 415
