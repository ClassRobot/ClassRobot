from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_planner_node_includes_user_message_for_plan_request(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.coordination.nodes import PlannerNode
    from src.core.agent.runtime.coordination.state import PipelineState
    from src.core.agent.runtime.schema import IntentRoute
    from src.core.llm.message import Content, Context, LLMRole, Messages

    pipeline = MessageProcessingPipeline(Helpers(), Messages(), trace_id="planner-user-message")
    captured: dict[str, object] = {}

    async def fake_ensure_mcp_tools() -> None:
        return None

    async def fake_create_llm_completion(messages: Messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"goal":"查询班级","requires_command":true,"should_execute":true,'
                            '"candidate_commands":["查询班级"],"steps":["查询班级"],"reason":"测试"}'
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(pipeline, "ensure_mcp_tools", fake_ensure_mcp_tools)
    monkeypatch.setattr(pipeline, "create_llm_completion", fake_create_llm_completion)

    state = PipelineState(
        trace_id="planner-user-message",
        user_content=[Content(type="text", value="我在哪个班级")],
        intent_route=IntentRoute(intent="command", requires_command=True),
        extracted_context=Context(role=LLMRole.user, content="我在哪个班级"),
    )

    await PlannerNode().run(pipeline, state)

    sent_messages = captured["messages"]
    assert isinstance(sent_messages, Messages)
    assert any(
        isinstance(message, Context)
        and message.role == LLMRole.user
        and message.single_modal() == "我在哪个班级"
        for message in sent_messages
    )
    assert state.agent_plan is not None
    assert state.agent_plan.goal == "查询班级"
