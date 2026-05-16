from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class DomesticProvider:
    """国内 OpenAI 兼容模型供应商配置模板。"""

    provider: str
    base_url: str
    key_env: str
    model_examples: tuple[str, ...] = ()
    supports_functools: bool = True
    multi_modal: bool = False
    notes: str = ""

    def build_config(
        self,
        *,
        name: str,
        key: str,
        model: str,
        proxy: str | None = None,
        priority: int = 100,
        tasks: list[str] | None = None,
        supports_functools: bool | None = None,
        multi_modal: bool | None = None,
    ) -> dict[str, object]:
        """生成可直接放入 `LLM_CONFIGS` 的单个模型配置。"""

        config: dict[str, object] = {
            "name": name,
            "key": key,
            "url": self.base_url,
            "model": model,
            "priority": priority,
            "tasks": tasks or ["chat", "tool", "summary", "extract", "plan", "reply"],
            "multi_modal": self.multi_modal if multi_modal is None else multi_modal,
            "supports_functools": self.supports_functools if supports_functools is None else supports_functools,
        }
        if proxy:
            config["proxy"] = proxy
        return config


DOMESTIC_PROVIDERS: dict[str, DomesticProvider] = {
    "volcengine_ark": DomesticProvider(
        provider="volcengine_ark",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        key_env="ARK_API_KEY",
        model_examples=("ep-xxxxxxxxxxxxxxxxxxxxx",),
        notes="火山方舟 OpenAI 兼容入口，model 通常是推理接入点 ID。",
    ),
    "deepseek": DomesticProvider(
        provider="deepseek",
        base_url="https://api.deepseek.com",
        key_env="DEEPSEEK_API_KEY",
        model_examples=("deepseek-v4-flash", "deepseek-v4-pro", "deepseek-reasoner"),
        notes="DeepSeek OpenAI 兼容入口。",
    ),
    "dashscope_qwen": DomesticProvider(
        provider="dashscope_qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        key_env="DASHSCOPE_API_KEY",
        model_examples=("qwen-plus", "qwen3.6-plus"),
        notes="阿里云百炼/通义千问 OpenAI 兼容入口，北京地域。",
    ),
    "moonshot_kimi": DomesticProvider(
        provider="moonshot_kimi",
        base_url="https://api.moonshot.ai/v1",
        key_env="MOONSHOT_API_KEY",
        model_examples=("kimi-latest",),
        notes="Moonshot/Kimi OpenAI 兼容入口。",
    ),
    "zhipu_glm": DomesticProvider(
        provider="zhipu_glm",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        key_env="ZAI_API_KEY",
        model_examples=("glm-4.7", "glm-5"),
        notes="智谱 GLM 通用 OpenAI 兼容入口；Coding Plan 可按需换成 coding endpoint。",
    ),
    "google_gemini": DomesticProvider(
        provider="google_gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_env="GOOGLE_API_KEY",
        model_examples=("gemini-2.5-flash", "gemini-2.5-pro"),
        multi_modal=True,
        notes="Google Gemini OpenAI 兼容入口，适合文本、工具调用和多模态场景。",
    ),
}


def get_domestic_provider(provider: str) -> DomesticProvider:
    """获取国内模型供应商配置模板。"""

    try:
        return DOMESTIC_PROVIDERS[provider]
    except KeyError as error:
        supported = ", ".join(sorted(DOMESTIC_PROVIDERS))
        raise ValueError(f"unsupported domestic provider {provider!r}; supported: {supported}") from error


def build_llm_config(
    provider: str,
    *,
    name: str,
    key: str,
    model: str,
    proxy: str | None = None,
    priority: int = 100,
    tasks: list[str] | None = None,
) -> dict[str, object]:
    """根据供应商名称生成 `LLM_CONFIGS` 中的一项配置。"""

    return get_domestic_provider(provider).build_config(
        name=name,
        key=key,
        model=model,
        proxy=proxy,
        priority=priority,
        tasks=tasks,
    )


def dumps_llm_configs(configs: list[dict[str, object]]) -> str:
    """把多模型配置格式化为适合写入 `.env` 的 JSON 字符串。"""

    return json.dumps(configs, ensure_ascii=False, indent=4)
