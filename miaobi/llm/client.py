from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from miaobi.config import Settings


class ModelConfigurationError(RuntimeError):
    pass


class ModelResponseError(RuntimeError):
    pass


def _json_text(content: str) -> str:
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    first = text.find("{")
    last = text.rfind("}")
    if first < 0 or last < first:
        raise ModelResponseError("模型没有返回 JSON 对象")
    return text[first : last + 1]


class OpenAICompatibleClient:
    def __init__(self, settings: Settings):
        if not settings.llm_configured:
            raise ModelConfigurationError("尚未配置可用的大模型")
        self.settings = settings

    @property
    def endpoint(self) -> str:
        return f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"

    async def complete_json(self, *, prompt: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
        started = time.perf_counter()
        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "temperature": 0,
            "max_tokens": self.settings.llm_max_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": self.settings.llm_enable_thinking},
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(self.endpoint, headers=headers, json=body)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ModelResponseError(f"模型服务返回 HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ModelResponseError("模型服务连接失败或超时") from exc
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelResponseError("模型响应缺少回答内容") from exc
        try:
            parsed = json.loads(_json_text(str(content)))
        except json.JSONDecodeError as exc:
            raise ModelResponseError("模型返回的 JSON 无法解析") from exc
        if not isinstance(parsed, dict):
            raise ModelResponseError("模型必须返回 JSON 对象")
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return parsed, elapsed_ms

    async def check(self) -> dict[str, Any]:
        result, elapsed_ms = await self.complete_json(
            prompt='只输出严格 JSON：{"ok": true}，不要输出其他内容。',
            payload={"task": "health_check"},
        )
        if result.get("ok") is not True:
            raise ModelResponseError("模型健康检查返回了非预期结果")
        return {"ok": True, "elapsed_ms": elapsed_ms}
