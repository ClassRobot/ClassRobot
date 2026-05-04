from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminPatchRequest(BaseModel):
    is_admin: bool


class StatusCheckRequest(BaseModel):
    targets: list[str] = Field(default_factory=list)


class SettingsPatchRequest(BaseModel):
    base: dict[str, Any] | None = None
    ai: dict[str, Any] | None = None
    cache: dict[str, Any] | None = None
    cos: dict[str, Any] | None = None
    security: dict[str, Any] | None = None
    models: dict[str, Any] | None = None


class PromptUpdateRequest(BaseModel):
    content: str


class ModelSettingsRequest(BaseModel):
    llm_timeout: float | None = None
    llm_configs: list[dict[str, Any]] | None = None
