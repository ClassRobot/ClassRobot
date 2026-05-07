from dataclasses import is_dataclass

import pytest


def test_auto_gpt_harness_builds_policy_context_and_observability(loaded_plugins):
    from utils.helper import Helper, Helpers
    from utils.llm.message import Messages
    from src.plugins.autogpt.harness import AutoGPTHarness
    from src.plugins.autogpt.knowledge import AgentRuntimeContext

    helpers = Helpers()
    helpers.append(Helper(command="我的信息", description="查询当前用户身份"))
    messages = Messages()

    harness = AutoGPTHarness.build(
        helpers=helpers,
        messages=messages,
        trace_id="autogpt-harness",
        runtime_context=AgentRuntimeContext(user_id=1, platform="qq", channel_id="test-channel"),
    )

    assert harness.helpers is helpers
    assert harness.messages is messages
    assert harness.trace_id == "autogpt-harness"
    assert harness.runtime_context is not None
    assert harness.command_tools.get("我的信息") is not None


@pytest.mark.asyncio
async def test_pipeline_report_progress_uses_harness_observability(loaded_plugins):
    from utils.helper import Helpers
    from utils.llm.message import Messages
    from src.plugins.autogpt.harness import AutoGPTHarness
    from src.plugins.autogpt.pipeline import MessageProcessingPipeline

    reports: list[str] = []

    async def report(message: str) -> None:
        reports.append(message)

    harness = AutoGPTHarness.build(
        helpers=Helpers(),
        messages=Messages(),
        trace_id="autogpt-harness-progress",
        progress_reporter=report,
    )
    pipeline = MessageProcessingPipeline(harness=harness)

    await pipeline.report_progress("我正在提取目标。", stage="extract")
    await pipeline.report_progress("我正在提取目标。", stage="extract")

    assert reports == ["extract: 我正在提取目标。"]


def test_chat_session_build_harness_reuses_session_messages(loaded_plugins):
    from utils.helper import Helpers
    from src.plugins.autogpt.util import ChatSession

    session = ChatSession(user_id=1, helpers=Helpers())
    session.last_trace_id = "autogpt-session-harness"

    harness = session.build_harness(trace_id=session.last_trace_id)

    assert harness.messages is session.messages
    assert harness.helpers is session.helpers
    assert harness.trace_id == "autogpt-session-harness"


def test_internal_runtime_models_use_dataclass_and_isolated_defaults(loaded_plugins):
    from src.plugins.autogpt.schema import ChatMessage
    from src.plugins.autogpt.pipeline import PipelineState, LocalChatStatisticsQuery
    from src.plugins.autogpt.knowledge import AgentRuntimeContext
    from utils.llm.message import Content

    assert is_dataclass(ChatMessage)
    assert is_dataclass(PipelineState)
    assert is_dataclass(LocalChatStatisticsQuery)
    assert is_dataclass(AgentRuntimeContext)

    first_message = ChatMessage()
    second_message = ChatMessage()
    first_message.message.append(Content(type="text", value="hello"))
    assert second_message.message == []

    first_state = PipelineState()
    second_state = PipelineState()
    first_state.user_content.append(Content(type="text", value="query"))
    assert second_state.user_content == []
