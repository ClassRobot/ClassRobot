import json
import re

import httpx
from nonebot import get_driver
from openai import AsyncOpenAI
from pydantic import BaseModel, Extra, Field, validator


class LLMConfig(BaseModel):
    """描述大模型服务连接与调用的配置项。"""

    class Config:
        """允许忽略额外字段，兼容环境配置里的扩展项。"""

        extra = Extra.ignore

    name: str
    key: str
    url: str
    model: str
    proxy: str | None = None
    """当前模型独立代理地址；为空时不为这个模型启用代理。"""
    priority: int = 0
    """模型路由优先级，数值越大越优先。"""
    tasks: list[str] = Field(default_factory=list)
    """偏好的任务类型，用于路由时优先匹配。"""
    multi_modal: bool = False
    """是否支持多模态。"""
    supports_functools: bool = False
    """是否支持函数工具调用。"""

    @validator("name", "key", "url", "model", pre=True, allow_reuse=True)
    def normalize_required_strings(cls, value: object) -> object:
        """去掉模型关键字段两端空白，避免环境变量里夹带空格。"""

        if isinstance(value, str):
            return value.strip()
        return value

    @validator("proxy", pre=True, allow_reuse=True)
    def normalize_proxy(cls, value: object) -> str | None | object:
        """把空白代理统一视为未设置。"""

        if value is None:
            return None
        if isinstance(value, str):
            proxy = value.strip()
            return proxy or None
        return value

    def build_async_openai_client(self) -> AsyncOpenAI:
        """按模型配置构造 OpenAI 兼容客户端。"""

        http_client: httpx.AsyncClient | None = None
        if self.proxy:
            http_client = httpx.AsyncClient(proxy=self.proxy)
        return AsyncOpenAI(
            api_key=self.key,
            base_url=self.url,
            http_client=http_client,
        )


class AutoGPTConfig(BaseModel):
    """描述 AutoGPT 会话与规划模块的配置项。"""

    class Config:
        """允许忽略额外字段，兼容运行时配置注入。"""

        extra = Extra.ignore

    llm_configs: list[LLMConfig] = Field(default_factory=list)
    llm_timeout: float = 20

    @validator("llm_configs", pre=True, allow_reuse=True)
    def normalize_llm_configs(cls, value: object) -> object:
        """兼容 `.env` 中以 JSON 字符串形式声明的模型配置列表。"""

        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            normalized = re.sub(r",(\s*[\]}])", r"\1", text)
            return json.loads(normalized)
        return value

    def get_config(self, name: str) -> LLMConfig:
        """按名称获取模型配置。"""

        for llm_config in self.llm_configs:
            if llm_config.name == name:
                return llm_config
        raise Exception(f"LLM config <{name}> not found")


plugin_config = AutoGPTConfig.parse_obj(get_driver().config)
