from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from utils.llm.config import plugin_config

from .service import mask_secret
from .settings_store import update_settings


def _config_payload(config, *, mask: bool = True) -> dict[str, Any]:
    payload = config.dict()
    if mask:
        payload["key"] = mask_secret(payload.get("key"))
    return payload


def list_models() -> dict[str, Any]:
    return {
        "llm_timeout": plugin_config.llm_timeout,
        "items": [_config_payload(config) for config in plugin_config.llm_configs],
    }


def save_models(payload: dict[str, Any]) -> dict[str, Any]:
    models_payload: dict[str, Any] = {}
    if "llm_timeout" in payload and payload["llm_timeout"] is not None:
        models_payload["llm_timeout"] = payload["llm_timeout"]
    if "llm_configs" in payload and payload["llm_configs"] is not None:
        models_payload["llm_configs"] = payload["llm_configs"]
    return update_settings({"models": models_payload})


async def test_model(name: str) -> dict[str, Any]:
    config = next((item for item in plugin_config.llm_configs if item.name == name), None)
    if config is None:
        raise KeyError(f"Model config `{name}` not found")

    client = AsyncOpenAI(api_key=config.key, base_url=config.url)
    response = await client.chat.completions.create(
        model=config.model,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=8,
        temperature=0,
        timeout=plugin_config.llm_timeout,
    )
    return {
        "ok": True,
        "name": config.name,
        "model": config.model,
        "response_id": response.id,
    }
