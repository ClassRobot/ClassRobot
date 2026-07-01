from __future__ import annotations

from types import SimpleNamespace

import pytest


class FakeChatCompletions:
    """捕获传给 OpenAI SDK 的请求参数。"""

    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    async def create(self, **kwargs):
        self.captured.update(kwargs)
        return SimpleNamespace(
            id="fake-response-id",
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        )


class FakeOpenAIClient:
    """提供最小化的 `chat.completions.create()` 测试替身。"""

    def __init__(self, captured: dict[str, object]) -> None:
        self.chat = SimpleNamespace(completions=FakeChatCompletions(captured))


@pytest.mark.asyncio
async def test_client_create_omits_unset_optional_fields(loaded_plugins, monkeypatch):
    import src.core.llm as llm_module
    from src.core.llm.config import LLMConfig

    config = LLMConfig(
        name="test-gateway-default",
        key="test-key",
        url="https://api.example.com/v1",
        model="gpt-test",
        supports_functools=True,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(llm_module.llm_gateway.router, "select", lambda request: [config])
    monkeypatch.setitem(llm_module.llm_gateway.clients, config.name, FakeOpenAIClient(captured))

    response = await llm_module.client_create(
        "你好",
        functools=None,
        tool_choice=None,
        temperature=None,
        llm_name=config.name,
        max_tokens=16,
    )

    assert response.id == "fake-response-id"
    assert captured["messages"] == [{"role": "user", "content": "你好"}]
    assert captured["model"] == config.model
    assert captured["max_tokens"] == 16
    assert "tools" not in captured
    assert "tool_choice" not in captured
    assert "temperature" not in captured


@pytest.mark.asyncio
async def test_client_create_keeps_explicit_tool_request_fields(loaded_plugins, monkeypatch):
    import src.core.llm as llm_module
    from src.core.llm.config import LLMConfig

    config = LLMConfig(
        name="test-gateway-tools",
        key="test-key",
        url="https://api.example.com/v1",
        model="gpt-test",
        supports_functools=True,
    )
    captured: dict[str, object] = {}
    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_user",
                "description": "查询用户信息",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]

    monkeypatch.setattr(llm_module.llm_gateway.router, "select", lambda request: [config])
    monkeypatch.setitem(llm_module.llm_gateway.clients, config.name, FakeOpenAIClient(captured))

    response = await llm_module.client_create(
        "帮我查询用户",
        functools=tools,
        tool_choice="auto",
        temperature=0.35,
        llm_name=config.name,
        max_tokens=32,
    )

    assert response.id == "fake-response-id"
    assert captured["tools"] == tools
    assert captured["tool_choice"] == "auto"
    assert captured["temperature"] == 0.35
    assert captured["model"] == config.model
    assert captured["max_tokens"] == 32


def test_core_llm_modules_import_from_canonical_entry(loaded_plugins):
    import src.core.llm.gateway as core_gateway_module
    import src.core.llm.message as core_message_module

    assert core_message_module.__name__ == "src.core.llm.message"
    assert core_gateway_module.__name__ == "src.core.llm.gateway"
