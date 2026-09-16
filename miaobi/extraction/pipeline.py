from __future__ import annotations

import hashlib
import json
from typing import Any, Type

from pydantic import BaseModel, ValidationError
from semantica.normalize import TextNormalizer
from semantica.split import TextSplitter

from miaobi.extraction.models import ParsedDocument
from miaobi.extraction.schemas import (
    ClaimEnvelope,
    EntityEnvelope,
    FactEnvelope,
    MetricEnvelope,
    RelationEnvelope,
    SampleProfileEnvelope,
)
from miaobi.llm.client import ModelResponseError, OpenAICompatibleClient


STEP_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "material_role", "title": "材料归类", "short_title": "归类",
        "input_label": "用户选择", "output_label": "材料用途", "execution_mode": "manual",
        "requires_model": False,
        "purpose": "明确材料是本次事实、制度依据、参考资料、样稿还是附件。",
        "principle": "材料用途由用户最终决定。系统不把样稿中的地名、数字和结论当成本次事实。",
        "writing_value": "决定后续内容能否作为事实引用，防止参考样稿污染新文章。",
        "guardrail": "模型可以推荐分类，但不能覆盖用户选择。",
        "prompt": "本步骤不调用大模型。材料用途以用户选择为准。",
    },
    {
        "key": "sample_profile", "title": "样稿结构", "short_title": "结构",
        "input_label": "样稿与格式", "output_label": "结构模板", "execution_mode": "model",
        "requires_model": True,
        "purpose": "提炼样稿的文种、目录、章节职责、语气和排版特征。",
        "principle": "模型只学习结构与表达方式，不继承样稿中的业务事实。",
        "writing_value": "让新文章在结构和文体上接近真实样稿，同时保持事实独立。",
        "guardrail": "不得输出或复用样稿中的具体地名、数值、日期、结论和正式权限。",
        "prompt": """你是专业文稿结构分析器。根据输入 Evidence 提取样稿结构，只输出严格 JSON 对象：
{"items":[{"document_type":"文种","audience":null,"tone":"语气","outline":["一级标题"],"section_responsibilities":["章节职责"],"formatting_notes":["格式特征"]}]}
规则：只分析结构、章节职责、文风和格式；不得把样稿中的地名、数值、时间和结论作为新文章事实；不得输出额外字段或解释。""",
    },
    {
        "key": "evidence", "title": "Evidence", "short_title": "Evidence",
        "input_label": "已解析正文", "output_label": "Evidence", "execution_mode": "deterministic",
        "requires_model": False,
        "purpose": "把原文整理为稳定、可定位的证据单元。",
        "principle": "解析器保留页码和结构位置，Semantica 负责归一化与语义完整切片；内容不由模型改写。",
        "writing_value": "后续每个对象、主张和事实都必须回指原文，是引用和联动更新的根。",
        "guardrail": "Evidence 必须保留原文、来源元素、页码、路径、字符区间和内容哈希。",
        "prompt": "本步骤不调用大模型，由解析器与 Semantica 确定性执行。",
    },
    {
        "key": "entity", "title": "Entity", "short_title": "Entity",
        "input_label": "Evidence", "output_label": "Entity", "execution_mode": "model",
        "requires_model": True,
        "purpose": "识别组织、地点、人物角色、制度、事件、资源、设施和指标等写作对象。",
        "principle": "模型提出对象候选，程序校验其 Evidence 引用并生成稳定 ID。",
        "writing_value": "统一名称和别名，为跨段落一致性、关系组织和后续检索建立锚点。",
        "guardrail": "属性值不能误当实体；每个 Entity 必须引用真实 Evidence；默认需要人工确认。",
        "prompt": """你是 Entity 抽取器。只依据输入 Evidence 识别对专业写作有意义的对象，只输出严格 JSON：
{"items":[{"name":"对象名称","entity_type":"组织|地点|角色|制度|事件|资源|设施|指标|其他","aliases":[],"evidence_ids":["真实Evidence ID"],"needs_confirmation":true}]}
规则：不得创造输入中不存在的对象；属性值不单独作为 Entity；evidence_ids 只能来自输入；不要输出 ID，服务端会生成；不得输出额外字段或解释。""",
    },
    {
        "key": "claim", "title": "Claim", "short_title": "Claim",
        "input_label": "Evidence + Entity", "output_label": "Claim", "execution_mode": "model",
        "requires_model": True,
        "purpose": "抽取材料明确表达的事实陈述、要求、预测、建议和观点。",
        "principle": "Claim 表示‘某个来源说了什么’，不等于已经核验为事实。",
        "writing_value": "把原文陈述与后续正式事实分开，防止把建议、预测或观点写成既成事实。",
        "guardrail": "每条 Claim 必须有主语、谓词、宾语、类型和 Evidence；不得跨片段补造。",
        "prompt": """你是 Claim 抽取器。只依据输入 Evidence 和 Entity 抽取来源明确表达的主张，只输出严格 JSON：
{"items":[{"subject":"主语","predicate":"谓词","object_text":"宾语或陈述值","claim_type":"fact_statement|requirement|forecast|recommendation|opinion","evidence_ids":["真实Evidence ID"],"needs_confirmation":true}]}
规则：Claim 只是来源主张，不代表已核验事实；不得推测隐含结论；evidence_ids 只能来自输入；不要输出 ID；不得输出额外字段或解释。""",
    },
    {
        "key": "fact", "title": "Fact", "short_title": "Fact",
        "input_label": "Claim + Evidence", "output_label": "Fact 候选", "execution_mode": "hybrid",
        "requires_model": True,
        "purpose": "把可核验的 Claim 整理为带时间、范围、单位和来源的事实候选。",
        "principle": "模型负责语义整理，程序严格校验 Claim 与 Evidence 引用；模型输出永远不是自动核验通过。",
        "writing_value": "正式写作引用稳定事实，而不是直接复制模型理解或含混原句。",
        "guardrail": "所有结果状态固定为 candidate，必须经过规则校验或人工确认后才能成为正式 Fact。",
        "prompt": """你是 Fact 候选整理器。根据输入 Claim 和 Evidence 整理可核验事实候选，只输出严格 JSON：
{"items":[{"claim_id":"真实Claim ID","subject":"主体","predicate":"谓词","object_value":"值","value_type":"text|number|date|boolean|reference","unit":null,"time_scope":null,"applicable_scope":null,"evidence_ids":["真实Evidence ID"],"needs_confirmation":true}]}
规则：只能使用输入 Claim；预测、建议和观点通常不能直接成为 Fact；保留单位、时间和适用范围；不要输出 ID 或 verified 状态；不得输出额外字段或解释。""",
    },
    {
        "key": "relation", "title": "Relation", "short_title": "Relation",
        "input_label": "Fact + Entity", "output_label": "Relation 候选", "execution_mode": "hybrid",
        "requires_model": True,
        "purpose": "把已整理事实表达为对象之间可追溯的关系候选。",
        "principle": "模型匹配语义关系，程序验证两个 Entity、Fact 和 Evidence 都真实存在。",
        "writing_value": "支持跨章节一致性、影响路径、关联检索和 Semantica 后续规则推演。",
        "guardrail": "无真实 Entity 或 Fact 支撑的关系会被拒绝；候选关系默认需要确认。",
        "prompt": """你是 Relation 整理器。只把输入 Fact 候选映射为输入 Entity 之间的直接关系，只输出严格 JSON：
{"items":[{"subject_entity_id":"真实Entity ID","predicate":"关系名称","object_entity_id":"真实Entity ID","fact_ids":["真实Fact ID"],"evidence_ids":["真实Evidence ID"],"needs_confirmation":true}]}
规则：识别 Fact 明确表达的组织职责、供应、使用、管理、发生于、需要等直接关系；不得创造 Entity、Fact 或 Evidence ID；每个 Relation 至少引用一个真实 Fact；没有 Fact 支撑时返回 {"items":[]}；不得进行多跳推演；不要输出 ID；不得输出额外字段或解释。""",
    },
    {
        "key": "metric", "title": "指标公式", "short_title": "指标",
        "input_label": "Fact + Evidence", "output_label": "指标与公式候选", "execution_mode": "hybrid",
        "requires_model": True,
        "purpose": "识别原子指标、派生指标、单位、公式候选和可能使用的章节。",
        "principle": "模型识别公式候选，程序和用户确认公式；正式数值由确定性计算引擎计算。",
        "writing_value": "建立输入变化到派生指标、正文段落和表格的依赖，为联动更新做准备。",
        "guardrail": "模型不得计算或写入权威数值；公式候选未经确认不能执行。",
        "prompt": """你是指标与公式识别器。依据 Fact 候选和 Evidence 识别写作需要的指标，只输出严格 JSON：
{"items":[{"name":"指标名","metric_type":"atomic|derived","value":null,"unit":null,"formula":null,"dependency_names":[],"evidence_ids":[],"target_section_hints":[],"needs_confirmation":true}]}
规则：输入中每个带数值和单位的业务量都应生成 atomic 指标；原文明确出现“某指标＝A－B”等口径时应生成 derived 指标及公式候选；原子指标必须有 Evidence；派生指标只提出公式候选和依赖名称，不得猜测权威计算结果；不得输出额外字段或解释。""",
    },
)


def step_definitions() -> list[dict[str, Any]]:
    return [dict(step) for step in STEP_DEFINITIONS]


def _chunks(document: ParsedDocument) -> list[dict[str, Any]]:
    normalizer = TextNormalizer(config={})
    splitter = TextSplitter(method="recursive", chunk_size=800, chunk_overlap=120)
    chunks: list[dict[str, Any]] = []
    ordinal = 0
    for element in document.elements:
        normalized = str(normalizer.normalize(element.text, unicode_form="NFKC", case="preserve"))
        for part in splitter.split(normalized):
            text = part.text.strip()
            if not text:
                continue
            digest = hashlib.sha256(
                f"{document.sha256}:{element.element_id}:{ordinal}:{text}".encode("utf-8")
            ).hexdigest()[:24]
            chunks.append({
                "id": digest, "element_id": element.element_id, "text": text,
                "page": element.page_number, "path": element.structural_path,
                "source_span": {"start": int(part.start_index), "end": int(part.end_index)},
                "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            })
            ordinal += 1
    return chunks


def build_preview(document: ParsedDocument, *, material_role: str) -> dict[str, Any]:
    evidence = _chunks(document)
    material = {
        "id": document.sha256[:24], "filename": document.filename, "role": material_role,
        "parser": document.parser, "element_count": len(document.elements), "sha256": document.sha256,
    }
    items = {"material_role": [material], "evidence": evidence}
    steps = step_definitions()
    for step in steps:
        step["items"] = items.get(step["key"], [])
        step["count"] = len(step["items"])
        step["status"] = "completed" if step["items"] else (
            "not_required" if step["key"] == "sample_profile" and material_role != "sample_style" else "not_run"
        )
        step["elapsed_ms"] = 0
    return {"document": material, "steps": steps, "summary": {"elements": len(document.elements), "evidence": len(evidence)}}


def _stable_result_id(step: str, item: dict[str, Any]) -> str:
    canonical = json.dumps(item, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(f"{step}:{canonical}".encode("utf-8")).hexdigest()[:24]


def _reference_subset(items: list[dict[str, Any]], field: str, allowed: set[str], step: str) -> None:
    for item in items:
        refs = item.get(field, [])
        if not isinstance(refs, list):
            refs = [refs]
        if any(str(ref) not in allowed for ref in refs):
            raise ModelResponseError(f"{step} 返回了输入中不存在的 {field}")


def _compact_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": item["id"], "text": str(item["text"])[:1400], "page": item.get("page"), "path": item.get("path")}
        for item in items[:60]
    ]


async def _model_step(
    client: OpenAICompatibleClient,
    *,
    key: str,
    payload: dict[str, Any],
    envelope: Type[BaseModel],
) -> tuple[list[dict[str, Any]], int]:
    definition = next(step for step in STEP_DEFINITIONS if step["key"] == key)
    raw, elapsed_ms = await client.complete_json(prompt=definition["prompt"], payload=payload)
    try:
        validated = envelope.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", []))
        repair_prompt = (
            f"{definition['prompt']}\n\n上一次输出没有通过严格 Schema 校验，错误位置为 {location}。"
            "请重新生成完整 JSON；不能确定或缺少合法引用的候选不要输出，使用空 items，不得放宽 Schema。"
        )
        repaired, retry_ms = await client.complete_json(prompt=repair_prompt, payload=payload)
        elapsed_ms += retry_ms
        try:
            validated = envelope.model_validate(repaired)
        except ValidationError as retry_exc:
            retry_first = retry_exc.errors()[0]
            retry_location = ".".join(str(part) for part in retry_first.get("loc", []))
            raise ModelResponseError(f"{definition['title']} 输出不符合 Schema：{retry_location}") from retry_exc
    rows = [item.model_dump(mode="json") for item in validated.items]
    for row in rows:
        row["id"] = _stable_result_id(key, row)
    return rows, elapsed_ms


async def run_model_extraction(
    document: ParsedDocument,
    *,
    material_role: str,
    client: OpenAICompatibleClient,
) -> dict[str, Any]:
    result = build_preview(document, material_role=material_role)
    by_key = {step["key"]: step for step in result["steps"]}
    evidence = by_key["evidence"]["items"]
    evidence_input = _compact_evidence(evidence)
    evidence_ids = {item["id"] for item in evidence}

    if material_role == "sample_style":
        rows, elapsed = await _model_step(client, key="sample_profile", payload={"evidence": evidence_input}, envelope=SampleProfileEnvelope)
        by_key["sample_profile"].update(items=rows, count=len(rows), status="completed", elapsed_ms=elapsed)
        for key in ("entity", "claim", "fact", "relation", "metric"):
            by_key[key].update(items=[], count=0, status="not_required", elapsed_ms=0)
        result["summary"].update({"sample_profiles": len(rows)})
        result["model"] = {"name": client.settings.llm_model, "provider": "openai-compatible"}
        return result

    entities, elapsed = await _model_step(client, key="entity", payload={"evidence": evidence_input}, envelope=EntityEnvelope)
    _reference_subset(entities, "evidence_ids", evidence_ids, "Entity")
    by_key["entity"].update(items=entities, count=len(entities), status="completed", elapsed_ms=elapsed)

    claims, elapsed = await _model_step(client, key="claim", payload={"evidence": evidence_input, "entities": entities}, envelope=ClaimEnvelope)
    _reference_subset(claims, "evidence_ids", evidence_ids, "Claim")
    by_key["claim"].update(items=claims, count=len(claims), status="completed", elapsed_ms=elapsed)

    facts, elapsed = await _model_step(client, key="fact", payload={"claims": claims, "evidence": evidence_input}, envelope=FactEnvelope)
    _reference_subset(facts, "evidence_ids", evidence_ids, "Fact")
    _reference_subset(facts, "claim_id", {item["id"] for item in claims}, "Fact")
    for item in facts:
        item["verification_status"] = "candidate"
        item["needs_confirmation"] = True
    by_key["fact"].update(items=facts, count=len(facts), status="completed", elapsed_ms=elapsed)

    relations, elapsed = await _model_step(
        client, key="relation", payload={"entities": entities, "facts": facts, "evidence": evidence_input}, envelope=RelationEnvelope
    )
    entity_ids = {item["id"] for item in entities}
    _reference_subset(relations, "subject_entity_id", entity_ids, "Relation")
    _reference_subset(relations, "object_entity_id", entity_ids, "Relation")
    _reference_subset(relations, "fact_ids", {item["id"] for item in facts}, "Relation")
    _reference_subset(relations, "evidence_ids", evidence_ids, "Relation")
    by_key["relation"].update(items=relations, count=len(relations), status="completed", elapsed_ms=elapsed)

    metrics, elapsed = await _model_step(client, key="metric", payload={"facts": facts, "evidence": evidence_input}, envelope=MetricEnvelope)
    _reference_subset(metrics, "evidence_ids", evidence_ids, "指标公式")
    for item in metrics:
        item["execution_status"] = "proposal_only"
        item["needs_confirmation"] = True
    by_key["metric"].update(items=metrics, count=len(metrics), status="completed", elapsed_ms=elapsed)

    result["summary"].update({
        "entities": len(entities), "claims": len(claims), "facts": len(facts),
        "relations": len(relations), "metrics": len(metrics),
    })
    result["model"] = {"name": client.settings.llm_model, "provider": "openai-compatible"}
    return result
