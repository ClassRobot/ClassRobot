from types import SimpleNamespace

import pytest


def build_llm_response(content: str) -> SimpleNamespace:
    """构造最小化的大模型响应对象，便于在单元测试中替身调用。"""

    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.mark.asyncio
async def test_visual_message_does_not_short_circuit_to_generic_reply(loaded_plugins, monkeypatch):
    from utils.helper import Helpers
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module

    captured: dict[str, object] = {}
    reports: list[str] = []

    async def fake_client_create(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return build_llm_response(
            '{"intent":"chat","reply":"这是一张动漫头像。","requires_command":false,"requires_rag":false,'
            '"need_confirm":false,"reason":"当前消息带有图片，需要继续进入视觉理解链路。"}'
        )

    async def report(message: str) -> None:
        reports.append(message)

    monkeypatch.setattr(pipeline_module, "client_create", fake_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="vision-route",
        progress_reporter=report,
    )
    state = pipeline_module.PipelineState(
        trace_id="vision-route",
        user_content=[
            Content(type="text", value="这张图是什么"),
            Content(type="image", value="https://example.com/avatar.png"),
        ],
    )
    pipeline.messages.user_message(state.user_content)

    await pipeline_module.IntentRouteNode().run(pipeline, state)

    assert state.auto_tasks is None
    assert state.intent_route is not None
    assert state.intent_route.reply == "这是一张动漫头像。"
    assert captured["kwargs"]["multi_modal"] is True
    assert captured["kwargs"]["task_type"].value == "vision"
    assert reports == []

    route_messages = captured["messages"]
    latest_message = route_messages.messages[-1]
    assert latest_message.content == state.user_content


@pytest.mark.asyncio
async def test_extract_agent_uses_latest_visual_message_as_multimodal_input(loaded_plugins, monkeypatch):
    from utils.llm.message import Content, Messages
    from utils.llm.agents import tools as tools_module

    captured: dict[str, object] = {}

    async def fake_client_create(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return build_llm_response(
            '{"role":"user","content":[{"type":"text","value":"用户正在询问图片中的动漫头像角色。"},'
            '{"type":"image","value":"https://example.com/avatar.png"}]}'
        )

    monkeypatch.setattr(tools_module, "client_create", fake_client_create)

    messages = Messages()
    messages.system_message("你是测试用系统提示词。")
    messages.user_message(
        [
            Content(type="text", value="这张图是什么"),
            Content(type="image", value="https://example.com/avatar.png"),
        ]
    )

    context = await tools_module.ExtractAgent().execute(messages)

    assert context.content[0].value == "用户正在询问图片中的动漫头像角色。"
    assert context.content[1].type == "image"
    assert captured["kwargs"]["multi_modal"] is True
    assert captured["kwargs"]["task_type"].value == "vision"

    extract_messages = captured["messages"]
    latest_message = extract_messages.messages[-1]
    assert latest_message.content == messages.messages[-1].content


@pytest.mark.asyncio
async def test_simple_visual_question_replies_directly_without_progress(loaded_plugins, monkeypatch):
    from utils.helper import Helpers
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module
    from src.plugins.autogpt.schema import ChatMessage

    calls: list[dict[str, object]] = []
    reports: list[str] = []

    async def fake_client_create(messages, **kwargs):
        calls.append({"messages": messages, "kwargs": kwargs})
        if len(calls) == 1:
            return build_llm_response(
                '{"intent":"vision_file","reply":null,"requires_command":false,"requires_rag":false,'
                '"need_confirm":false,"reason":"用户在直接询问图片内容。"}'
            )
        if len(calls) == 2:
            return build_llm_response("这是一张紫色调的二次元女生头像。")
        raise AssertionError("simple visual reply should not continue into planner/extract nodes")

    async def report(message: str) -> None:
        reports.append(message)

    monkeypatch.setattr(pipeline_module, "client_create", fake_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="vision-direct",
        progress_reporter=report,
    )

    result = await pipeline.process(
        ChatMessage(
            message=[
                Content(type="text", value="这张图是什么"),
                Content(type="image", value="https://example.com/avatar.png"),
            ]
        )
    )

    assert result.auto_tasks is not None
    assert result.auto_tasks.reply == "这是一张紫色调的二次元女生头像。"
    assert result.auto_tasks.need_confirm is False
    assert reports == []
    assert len(calls) == 2
    assert calls[0]["kwargs"]["task_type"].value == "vision"
    assert calls[1]["kwargs"]["task_type"].value == "vision"
