from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from miaobi.extraction.parser import parse_document_bytes
from miaobi.extraction.pipeline import build_preview, step_definitions


router = APIRouter(prefix="/extraction", tags=["extraction"])


@router.get("/steps")
def list_steps() -> list[dict]:
    return step_definitions()


@router.post("/preview")
async def preview_extraction(
    file: UploadFile = File(...),
    material_role: str = Form("reference"),
) -> dict:
    if material_role not in {"policy_basis", "task_data", "reference", "sample_style", "attachment"}:
        raise HTTPException(status_code=422, detail="材料用途不正确")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="文件内容为空")
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="MVP 单文件不能超过 30MB")
    try:
        parsed = parse_document_bytes(file.filename or "untitled", file.content_type, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return build_preview(parsed, material_role=material_role)

