from __future__ import annotations

from typing import Any

from src.core.llm.config import plugin_config

from ..service import mask_secret
from ..runtime.settings import update_settings


def _config_payload(config, *, mask: bool = True) -> dict[str, Any]:
    """序列化单个模型配置。

    Args:
        config: ``LLMConfig`` 实例。
        mask: 是否对 API key 做脱敏。

    Returns:
        dict[str, Any]: 可供管理端直接消费的模型配置字典。
    """
    payload = config.model_dump(exclude_none=True)
    if mask:
        payload["key"] = mask_secret(payload.get("key"))
    return payload


def list_models() -> dict[str, Any]:
    """返回当前模型配置列表。

    Returns:
        dict[str, Any]: 模型超时配置和模型条目列表。
    """
    return {
        "llm_timeout": plugin_config.llm_timeout,
        "items": [_config_payload(config) for config in plugin_config.llm_configs],
    }


def save_models(payload: dict[str, Any]) -> dict[str, Any]:
    """保存模型相关配置。

    Args:
        payload: 前端提交的模型设置局部更新数据。

    Returns:
        dict[str, Any]: settings_store 返回的保存结果。
    """
    models_payload: dict[str, Any] = {}
    if "llm_timeout" in payload and payload["llm_timeout"] is not None:
        models_payload["llm_timeout"] = payload["llm_timeout"]
    if "llm_configs" in payload and payload["llm_configs"] is not None:
        models_payload["llm_configs"] = payload["llm_configs"]
    return update_settings({"models": models_payload})


async def test_model(name: str) -> dict[str, Any]:
    """测试指定模型配置是否可用。

    Args:
        name: 模型配置名称。

    Returns:
        dict[str, Any]: 测试结果和响应标识信息。

    Raises:
        KeyError: 当模型配置不存在时抛出。
    """
    config = next((item for item in plugin_config.llm_configs if item.name == name), None)
    if config is None:
        raise KeyError(f"Model config `{name}` not found")

    client = config.build_async_openai_client()
    try:
        response = await client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
            temperature=0,
            timeout=plugin_config.llm_timeout,
        )
    finally:
        await client.close()
    return {
        "ok": True,
        "name": config.name,
        "model": config.model,
        "response_id": response.id,
    }
