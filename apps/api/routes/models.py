from __future__ import annotations

from fastapi import APIRouter, HTTPException

from miaobi.config import get_settings
from miaobi.llm.client import ModelConfigurationError, ModelResponseError, OpenAICompatibleClient


router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status")
def model_status() -> dict:
    settings = get_settings()
    return {
        "configured": settings.llm_configured,
        "provider": "openai-compatible" if settings.llm_configured else None,
        "model": settings.llm_model or None,
        "enable_thinking": settings.llm_enable_thinking,
    }


@router.post("/check")
async def check_model() -> dict:
    settings = get_settings()
    try:
        result = await OpenAICompatibleClient(settings).check()
    except ModelConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModelResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {**result, "model": settings.llm_model, "provider": "openai-compatible"}
