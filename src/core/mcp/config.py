from __future__ import annotations

import json
import os
from typing import Any

from nonebot import get_driver
from pydantic import Extra, Field, BaseModel, validator

from .schema import MCPTransport


class MCPConfig(BaseModel):
    """MCP Client 启动级配置。

    这些配置来自 `.env` / NoneBot driver config，属于启动级硬配置；
    运行时热更新配置不写回这里。
    """

    class Config:
        extra = Extra.ignore
        allow_population_by_field_name = True

    enabled: bool = Field(default=False, alias="mcp_enabled")
    server_url: str = Field(default="http://127.0.0.1:8000/mcp", alias="mcp_server_url")
    transport: MCPTransport = Field(default="streamable_http", alias="mcp_transport")
    timeout: float = Field(default=10.0, alias="mcp_timeout")
    auth_token: str | None = Field(default=None, alias="mcp_auth_token")
    tool_allowlist: list[str] = Field(default_factory=list, alias="mcp_tool_allowlist")

    @validator("enabled", pre=True, allow_reuse=True)
    def normalize_bool(cls, value: object) -> bool:
        """兼容 dotenv 中常见的布尔文本。"""

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @validator("server_url", pre=True, allow_reuse=True)
    def normalize_server_url(cls, value: object) -> str:
        """清理服务地址，并补足默认值。"""

        if value is None:
            return "http://127.0.0.1:8000/mcp"
        text = str(value).strip()
        return text or "http://127.0.0.1:8000/mcp"

    @validator("transport", pre=True, allow_reuse=True)
    def normalize_transport(cls, value: object) -> str:
        """当前优先使用 Streamable HTTP，保留 SSE 兼容配置位。"""

        text = str(value or "streamable_http").strip().lower()
        if text in {"streamable-http", "streamablehttp"}:
            return "streamable_http"
        return text

    @validator("timeout", pre=True, allow_reuse=True)
    def normalize_timeout(cls, value: object) -> float:
        """避免把非法超时配置传给 HTTP 客户端。"""

        try:
            timeout = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 10.0
        return max(timeout, 0.1)

    @validator("auth_token", pre=True, allow_reuse=True)
    def normalize_auth_token(cls, value: object) -> str | None:
        """空白 token 视为未配置。"""

        if value is None:
            return None
        token = str(value).strip()
        return token or None

    @validator("tool_allowlist", pre=True, allow_reuse=True)
    def normalize_allowlist(cls, value: object) -> list[str]:
        """支持 JSON 数组或逗号分隔字符串。"""

        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                parsed = json.loads(text)
                if not isinstance(parsed, list):
                    raise ValueError("mcp_tool_allowlist must be a JSON list")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]
        return [str(value).strip()]

    @property
    def headers(self) -> dict[str, str]:
        """构造 MCP 请求头，避免把凭据暴露给 prompt。"""

        if not self.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}

    @property
    def allowlist_set(self) -> set[str]:
        """返回去重后的工具白名单。"""

        return set(self.tool_allowlist)

    def is_tool_allowed(self, name: str) -> bool:
        """判断工具是否允许暴露给 Agent。"""

        allowlist = self.allowlist_set
        return not allowlist or name in allowlist


def load_mcp_config() -> MCPConfig:
    """从 NoneBot driver config 和环境变量读取 MCP 配置。"""

    data: dict[str, Any] = {}
    try:
        driver_config = get_driver().config
        for key in (
            "mcp_enabled",
            "mcp_server_url",
            "mcp_transport",
            "mcp_timeout",
            "mcp_auth_token",
            "mcp_tool_allowlist",
        ):
            value = getattr(driver_config, key, None)
            if value is not None:
                data[key] = value
    except Exception:
        pass

    env_key_map = {
        "MCP_ENABLED": "mcp_enabled",
        "MCP_SERVER_URL": "mcp_server_url",
        "MCP_TRANSPORT": "mcp_transport",
        "MCP_TIMEOUT": "mcp_timeout",
        "MCP_AUTH_TOKEN": "mcp_auth_token",
        "MCP_TOOL_ALLOWLIST": "mcp_tool_allowlist",
    }
    for env_key, config_key in env_key_map.items():
        if env_key in os.environ:
            data[config_key] = os.environ[env_key]
    return MCPConfig.parse_obj(data)
