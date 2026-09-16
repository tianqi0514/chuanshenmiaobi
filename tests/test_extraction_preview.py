from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from apps.api.main import app
from miaobi.extraction.parser import parse_document_bytes
from miaobi.extraction.pipeline import build_preview, run_model_extraction


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
    model_status = client.get("/api/v1/models/status")
    assert model_status.status_code == 200
    assert "api_key" not in model_status.json()
    steps = client.get("/api/v1/extraction/steps")
    assert steps.status_code == 200
    assert len(steps.json()) == 8
    assert [step["title"] for step in steps.json()[2:7]] == ["Evidence", "Entity", "Claim", "Fact", "Relation"]
    assert all("principle" in step and "guardrail" in step for step in steps.json())
    assert all("严格 JSON" in step["prompt"] for step in steps.json() if step["requires_model"])
    response = client.post(
        "/api/v1/extraction/preview",
        data={"material_role": "task_data"},
        files={"file": ("简报.txt", "震级为6.2级。".encode(), "text/plain")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["document"]["filename"] == "简报.txt"
    assert response.json()["summary"]["evidence"] == 1


class FakeStructuredClient:
    settings = SimpleNamespace(llm_model="test-structured-model")

    async def complete_json(self, *, prompt: str, payload: dict) -> tuple[dict, int]:
        evidence_id = payload.get("evidence", [{}])[0].get("id")
        if "专业文稿结构分析器" in prompt:
            return {"items": [{
                "document_type": "应急方案", "audience": "指挥人员", "tone": "正式",
                "outline": ["总体情况"], "section_responsibilities": ["说明事件"],
                "formatting_notes": ["分级标题"],
            }]}, 9
        if "Entity 抽取器" in prompt:
            return {"items": [
                {"name": "东方智造", "entity_type": "组织", "aliases": [], "evidence_ids": [evidence_id], "needs_confirmation": True},
                {"name": "NexusOne", "entity_type": "资源", "aliases": [], "evidence_ids": [evidence_id], "needs_confirmation": True},
            ]}, 10
        if "Claim 抽取器" in prompt:
            return {"items": [{
                "subject": "东方智造", "predicate": "供应", "object_text": "NexusOne",
                "claim_type": "fact_statement", "evidence_ids": [evidence_id], "needs_confirmation": True,
            }]}, 11
        if "Fact 候选整理器" in prompt:
            return {"items": [{
                "claim_id": payload["claims"][0]["id"], "subject": "东方智造", "predicate": "供应",
                "object_value": "NexusOne", "value_type": "reference", "unit": None,
                "time_scope": None, "applicable_scope": None, "evidence_ids": [evidence_id], "needs_confirmation": True,
            }]}, 12
        if "Relation 整理器" in prompt:
            return {"items": [{
                "subject_entity_id": payload["entities"][0]["id"], "predicate": "供应",
                "object_entity_id": payload["entities"][1]["id"], "fact_ids": [payload["facts"][0]["id"]],
                "evidence_ids": [evidence_id], "needs_confirmation": True,
            }]}, 13
        if "指标与公式识别器" in prompt:
            return {"items": []}, 14
        raise AssertionError("unexpected prompt")


def test_five_layer_pipeline_keeps_real_references_and_candidate_boundaries() -> None:
    document = parse_document_bytes(
        "供应说明.md", "text/markdown", "东方智造供应 NexusOne。".encode("utf-8")
    )
    result = asyncio.run(run_model_extraction(
        document, material_role="task_data", client=FakeStructuredClient()  # type: ignore[arg-type]
    ))
    steps = {step["key"]: step for step in result["steps"]}
    evidence_id = steps["evidence"]["items"][0]["id"]
    assert steps["entity"]["items"][0]["evidence_ids"] == [evidence_id]
    assert steps["claim"]["items"][0]["evidence_ids"] == [evidence_id]
    assert steps["fact"]["items"][0]["verification_status"] == "candidate"
    assert steps["fact"]["items"][0]["needs_confirmation"] is True
    assert steps["relation"]["items"][0]["fact_ids"] == [steps["fact"]["items"][0]["id"]]
    assert result["model"]["name"] == "test-structured-model"


def test_sample_style_extracts_structure_but_never_business_facts() -> None:
    document = parse_document_bytes("样稿.md", "text/markdown", "# 总体情况\n测试地区发生事件。".encode())
    result = asyncio.run(run_model_extraction(
        document, material_role="sample_style", client=FakeStructuredClient()  # type: ignore[arg-type]
    ))
    steps = {step["key"]: step for step in result["steps"]}
    assert steps["sample_profile"]["count"] == 1
    assert all(steps[key]["status"] == "not_required" for key in ("entity", "claim", "fact", "relation", "metric"))
