from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from miaobi.config import get_settings
from miaobi.db import get_db
from miaobi.extraction.parser import parse_document_bytes
from miaobi.extraction.pipeline import run_model_extraction
from miaobi.llm.client import ModelConfigurationError, ModelResponseError, OpenAICompatibleClient
from miaobi.persistence.models import ExtractionRun, Project, utcnow
from miaobi.persistence.storage import save_source_file


router = APIRouter(prefix="/projects", tags=["projects"])
MATERIAL_ROLES = {"policy_basis", "task_data", "reference", "sample_style", "attachment"}


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)


def _project_json(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


def _run_json(run: ExtractionRun, *, include_result: bool = False) -> dict:
    payload = {
        "id": run.id,
        "project_id": run.project_id,
        "filename": run.filename,
        "material_role": run.material_role,
        "status": run.status,
        "model_name": run.model_name,
        "summary": run.summary_json or {},
        "error": run.error_message,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
    if include_result:
        payload["result"] = run.result_json
    return payload


def _get_project(project_id: str, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.post("")
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    project = Project(name=body.name)
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="项目名称已存在") from exc
    db.refresh(project)
    return _project_json(project)


@router.get("")
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    projects = db.scalars(select(Project).order_by(Project.updated_at.desc())).all()
    return [_project_json(project) for project in projects]


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    return _project_json(_get_project(project_id, db))


@router.get("/{project_id}/runs")
def list_project_runs(project_id: str, db: Session = Depends(get_db)) -> list[dict]:
    _get_project(project_id, db)
    runs = db.scalars(
        select(ExtractionRun)
        .where(ExtractionRun.project_id == project_id)
        .order_by(ExtractionRun.created_at.desc())
    ).all()
    return [_run_json(run) for run in runs]


@router.get("/{project_id}/runs/{run_id}")
def get_project_run(project_id: str, run_id: str, db: Session = Depends(get_db)) -> dict:
    _get_project(project_id, db)
    run = db.scalar(select(ExtractionRun).where(
        ExtractionRun.id == run_id,
        ExtractionRun.project_id == project_id,
    ))
    if run is None:
        raise HTTPException(status_code=404, detail="抽取记录不存在")
    return _run_json(run, include_result=True)


@router.post("/{project_id}/extractions/run")
async def run_project_extraction(
    project_id: str,
    file: UploadFile = File(...),
    material_role: str = Form("reference"),
    db: Session = Depends(get_db),
) -> dict:
    project = _get_project(project_id, db)
    if material_role not in MATERIAL_ROLES:
        raise HTTPException(status_code=422, detail="材料用途不正确")
    data = await file.read()
    filename = file.filename or "untitled"
    if len(filename) > 255:
        raise HTTPException(status_code=422, detail="文件名不能超过 255 个字符")
    if not data:
        raise HTTPException(status_code=422, detail="文件内容为空")
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="MVP 单文件不能超过 30MB")

    run = ExtractionRun(
        project_id=project.id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        material_role=material_role,
        source_path="pending",
        status="running",
        model_name=get_settings().llm_model or None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        run.source_path = save_source_file(
            project_id=project.id, run_id=run.id, filename=run.filename, data=data
        )
        db.commit()
        parsed = parse_document_bytes(run.filename, run.content_type, data)
        client = OpenAICompatibleClient(get_settings())
        result = await run_model_extraction(parsed, material_role=material_role, client=client)
    except (ValueError, ModelConfigurationError, ModelResponseError) as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.completed_at = utcnow()
        project.updated_at = utcnow()
        db.commit()
        status_code = 422 if isinstance(exc, ValueError) else 503 if isinstance(exc, ModelConfigurationError) else 502
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        run.status = "failed"
        run.error_message = "抽取服务发生内部错误"
        run.completed_at = utcnow()
        project.updated_at = utcnow()
        db.commit()
        raise HTTPException(status_code=500, detail=run.error_message) from exc

    run.status = "completed"
    run.summary_json = result.get("summary", {})
    run.result_json = result
    run.completed_at = utcnow()
    project.updated_at = utcnow()
    db.commit()
    db.refresh(run)
    return _run_json(run, include_result=True)
