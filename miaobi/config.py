from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_base_url: str = Field(default="", alias="MIAOBI_LLM_BASE_URL")
    llm_model: str = Field(default="", alias="MIAOBI_LLM_MODEL")
    llm_api_key: str = Field(default="", alias="MIAOBI_LLM_API_KEY")
    llm_timeout_seconds: float = Field(default=120, alias="MIAOBI_LLM_TIMEOUT_SECONDS")
    llm_max_tokens: int = Field(default=4096, alias="MIAOBI_LLM_MAX_TOKENS")
    llm_enable_thinking: bool = Field(default=False, alias="MIAOBI_LLM_ENABLE_THINKING")

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url.strip() and self.llm_model.strip() and self.llm_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
