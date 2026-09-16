from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app
from miaobi.extraction.parser import parse_document_bytes
from miaobi.extraction.pipeline import build_preview


def test_markdown_is_parsed_as_text_and_not_ocr() -> None:
    document = parse_document_bytes("依据.md", "text/markdown", "# 总则\n本方案适用于测试项目。".encode())
    assert document.parser == "text"
    assert document.elements[0].structural_path == "document"
    preview = build_preview(document, material_role="policy_basis")
    assert preview["summary"]["evidence"] == 1
    assert preview["steps"][0]["items"][0]["role"] == "policy_basis"
    assert preview["steps"][2]["status"] == "completed"
    assert preview["steps"][3]["status"] == "not_run"


def test_api_exposes_prompts_and_real_preview() -> None:
    client = TestClient(app)
    steps = client.get("/api/v1/extraction/steps")
    assert steps.status_code == 200
    assert len(steps.json()) == 8
    assert all("严格 JSON" in step["prompt"] for step in steps.json())
    response = client.post(
        "/api/v1/extraction/preview",
        data={"material_role": "task_data"},
        files={"file": ("简报.txt", "震级为6.2级。".encode(), "text/plain")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["document"]["filename"] == "简报.txt"
    assert response.json()["summary"]["evidence"] == 1

