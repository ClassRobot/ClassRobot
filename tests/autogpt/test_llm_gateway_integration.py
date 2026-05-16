from __future__ import annotations

from types import SimpleNamespace

import pytest
from openai import NotGiven


class FakeChatCompletions:
    """为 AutoGPT 调用链提供最小化的 OpenAI 客户端替身。"""

    def __init__(self, captured: dict[str, object]) -> None:
        self.captured = captured

    async def create(self, **kwargs):
        for key, value in kwargs.items():
            if isinstance(value, NotGiven):
                raise AssertionError(f"request kwargs should not include NotGiven for {key}")
        self.captured.update(kwargs)
        return SimpleNamespace(
            id="pipeline-response-id",
            choices=[SimpleNamespace(message=SimpleNamespace(content="路由完成"))],
        )


class FakeOpenAIClient:
    """提供 `chat.completions.create()` 的最小调用面。"""

    def __init__(self, captured: dict[str, object]) -> None:
        self.chat = SimpleNamespace(completions=FakeChatCompletions(captured))


@pytest.mark.asyncio
async def test_pipeline_create_llm_completion_uses_gateway_without_sentinel_payload(loaded_plugins, monkeypatch):
    from utils.helper import Helpers
    import core.llm as llm_module
    from core.agent.runtime import pipeline as pipeline_module
    from core.llm import LLMTaskType
    from core.llm.config import LLMConfig
    from core.llm.message import Messages

    config = LLMConfig(
        name="test-pipeline-gateway",
        key="test-key",
        url="https://api.example.com/v1",
        model="gpt-test",
        supports_functools=True,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(llm_module.llm_gateway.router, "select", lambda request: [config])
    monkeypatch.setitem(llm_module.llm_gateway.clients, config.name, FakeOpenAIClient(captured))

    pipeline = pipeline_module.MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="gateway-integration",
    )
    messages = Messages()
    messages.system_message("你是测试用系统提示词。")
    messages.user_message("你好")

    response = await pipeline.create_llm_completion(
        messages,
        llm_name=config.name,
        multi_modal=False,
        max_tokens=24,
        task_type=LLMTaskType.plan,
    )

    assert response.id == "pipeline-response-id"
    assert captured["model"] == config.model
    assert captured["max_tokens"] == 24
    assert captured["temperature"] == 0.1
    assert "tools" not in captured
    assert "tool_choice" not in captured
