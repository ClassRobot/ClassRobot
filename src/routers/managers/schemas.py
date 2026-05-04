from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """本地管理后台登录页提交的启动令牌。"""

    token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """启动令牌登录成功后返回的短期会话令牌。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminPatchRequest(BaseModel):
    """切换用户本地管理员状态的请求体。"""

    is_admin: bool


class StatusCheckRequest(BaseModel):
    """按需执行状态检查的请求体；为空时表示检查全部分组。"""

    targets: list[str] = Field(default_factory=list)


class SettingsPatchRequest(BaseModel):
    """按管理后台设置面板分组提交的局部更新请求。"""

    base: dict[str, Any] | None = None
    ai: dict[str, Any] | None = None
    cache: dict[str, Any] | None = None
    cos: dict[str, Any] | None = None
    security: dict[str, Any] | None = None
    models: dict[str, Any] | None = None


class PromptUpdateRequest(BaseModel):
    """Prompt 编辑器提交的新模板内容。"""

    content: str


class ModelSettingsRequest(BaseModel):
    """模型配置更新请求体。"""

    llm_timeout: float | None = None
    llm_configs: list[dict[str, Any]] | None = None


class DatabaseRowUpdateRequest(BaseModel):
    """通用数据库行更新请求。

    Attributes:
        pk: 用于定位目标行的主键字段映射。
        values: 需要更新的列和值映射。
    """

    pk: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Any] = Field(default_factory=dict)


class TerminalExecuteRequest(BaseModel):
    """运维页直接执行终端命令的请求体。"""

    command: str = Field(min_length=1)
    cwd: str | None = None
    timeout: int = Field(default=300, ge=1, le=600)


class AutomationScriptCreateRequest(BaseModel):
    """在管理后台脚本库中创建一条可复用自动化脚本。"""

    id: str | None = None
    title: str = Field(min_length=1)
    description: str = ""
    command: str = Field(min_length=1)
    cwd: str | None = None
    risk: str = "medium"
    timeout: int = Field(default=300, ge=1, le=600)
    enabled: bool = True


class AutomationScriptUpdateRequest(BaseModel):
    """更新现有自动化脚本的局部字段。"""

    title: str | None = None
    description: str | None = None
    command: str | None = None
    cwd: str | None = None
    risk: str | None = None
    timeout: int | None = Field(default=None, ge=1, le=600)
    enabled: bool | None = None
