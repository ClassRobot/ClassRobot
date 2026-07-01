from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_group_history_context_is_not_injected_into_intent_route_prompt(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.schema import ChatMessage
    from src.core.agent.runtime import pipeline as pipeline_module
    from src.core.llm.message import Content, Context, LLMRole, Messages

    captured = {"prompt": ""}

    async def fake_client_create(messages, *args, **kwargs):
        system_text = "\n".join(
            message.single_modal()
            for message in messages.messages
            if isinstance(message, Context) and message.role == LLMRole.system
        )
        captured["prompt"] = system_text
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"intent":"chat","reply":"我已经准备好了。","requires_rag":false,"requires_command":false,"need_confirm":false,"reason":"普通闲聊"}'
                    )
                )
            ]
        )

    monkeypatch.setattr(pipeline_module, "client_create", fake_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        helpers=Helpers(),
        messages=Messages(),
        trace_id="group-history-context-disabled",
    )

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="刚才大家在聊什么")]))

    assert "当前群聊检索上下文" not in captured["prompt"]
    assert result.auto_tasks is not None
    assert result.auto_tasks.reply == "我已经准备好了。"
