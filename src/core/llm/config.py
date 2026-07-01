import re
import json

import httpx
from nonebot import get_driver
from openai import AsyncOpenAI
from pydantic import Field, BaseModel, ConfigDict, field_validator


class LLMConfig(BaseModel):
    """描述大模型服务连接与调用的配置项。"""

    model_config = ConfigDict(extra="ignore")

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

    @field_validator("name", "key", "url", "model", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> object:
        """去掉模型关键字段两端空白，避免环境变量里夹带空格。"""

        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("proxy", mode="before")
    @classmethod
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

    model_config = ConfigDict(extra="ignore")

    llm_configs: list[LLMConfig] = Field(default_factory=list)
    llm_timeout: float = 20
    agent_loop_max_steps: int = 8
    """单轮 Agent observe-act 循环最多执行多少步。"""
    agent_loop_max_verify_attempts: int = 3
    """同一目标最多验证多少次。"""
    agent_loop_max_repeat_actions: int = 2
    """同一命令和同一参数最多重复多少次。"""
    agent_loop_max_runtime_seconds: int = 120
    """单轮 Agent observe-act 循环最长运行秒数。"""

    @field_validator("llm_configs", mode="before")
    @classmethod
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


plugin_config = AutoGPTConfig.model_validate(get_driver().config.model_dump())
