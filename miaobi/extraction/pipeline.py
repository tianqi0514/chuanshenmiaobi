from __future__ import annotations

import hashlib
from typing import Any

from semantica.normalize import TextNormalizer
from semantica.split import TextSplitter

from miaobi.extraction.models import ParsedDocument


STEP_DEFINITIONS = (
    ("material_role", "材料归类", "归类", "项目材料", "材料用途", "判断材料在本次写作中的用途；样稿不得作为本次事实。"),
    ("sample_profile", "样稿结构", "结构", "样稿与格式", "结构模板", "只提取样稿的目录、章节职责和文风，不继承地名、数字或结论。"),
    ("evidence", "证据切片", "证据", "已解析正文", "Evidence", "按语义完整性整理证据单元，保留页码、结构位置和原文。"),
    ("entity", "对象识别", "对象", "Evidence", "Entity", "识别组织、地点、制度、资源、事件和指标，不把属性值误当实体。"),
    ("claim", "主张抽取", "主张", "Evidence + Entity", "Claim", "抽取来源明确陈述的主张，区分事实陈述、要求、预测、建议和观点。"),
    ("fact", "事实核验", "事实", "Claim + Evidence", "Fact", "核对来源版本、时间、范围和冲突；证据不足时不得形成正式事实。"),
    ("relation", "关系整理", "关系", "Fact + Entity", "Relation", "把已核验事实整理为对象关系，并回指 Fact、Claim 和 Evidence。"),
    ("metric", "指标公式", "指标", "Fact + 表格", "Metric / Formula", "识别原子指标、派生指标和依赖；公式候选必须经人工确认后才能执行。"),
)


def _prompt(title: str, purpose: str, output: str) -> str:
    return (
        f"你是妙笔的{title}执行器。\n\n任务：{purpose}\n\n"
        "规则：\n1. 只使用输入中存在的内容，不得补造事实。\n"
        "2. 每个结果必须保留来源对象 ID。\n3. 不确定内容标记 needs_confirmation=true。\n"
        f"4. 只输出严格 JSON，输出对象类型为 {output}。"
    )


def step_definitions() -> list[dict[str, Any]]:
    return [
        {
            "key": key, "title": title, "short_title": short, "input_label": source,
            "output_label": output, "purpose": purpose, "prompt": _prompt(title, purpose, output),
        }
        for key, title, short, source, output, purpose in STEP_DEFINITIONS
    ]


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
                "id": digest,
                "element_id": element.element_id,
                "text": text,
                "page": element.page_number,
                "path": element.structural_path,
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
    return {
        "document": material,
        "steps": steps,
        "summary": {"elements": len(document.elements), "evidence": len(evidence)},
    }

