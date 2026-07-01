import pytest


@pytest.mark.parametrize(
    ("intent", "requires_rag", "requires_command", "expected"),
    [
        ("chat", False, False, ""),
        ("violation", False, False, ""),
        ("vision_file", False, False, "我会先理解图片或文件内容，再根据你的问题给出可直接使用的结论。"),
        ("knowledge", True, False, "我会先检索相关资料，把命中的内容压缩成可用上下文后再回答。"),
        ("command", False, True, "我会把你的需求转换成系统内命令，确认参数后调用现有功能返回结果。"),
        ("complex_task", True, True, "我会先检索相关上下文，再把能执行的系统命令串起来处理。"),
    ],
)
def test_build_user_progress_message(loaded_plugins, intent, requires_rag, requires_command, expected):
    from src.core.agent.runtime.schema import IntentRoute
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    route = IntentRoute(
        intent=intent,
        requires_rag=requires_rag,
        requires_command=requires_command,
    )

    assert MessageProcessingPipeline.build_user_progress_message(route) == expected


def test_format_progress_message_hides_internal_stage_tags(loaded_plugins):
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    assert MessageProcessingPipeline.format_progress_message("我正在提取这轮对话里的目标。", stage="extract") == ""
    assert (
        MessageProcessingPipeline.format_progress_message("rag: 我正在检索相关资料。", stage="rag")
        == "我正在检索相关资料。"
    )


@pytest.mark.asyncio
async def test_report_progress_deduplicates_messages(loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.llm.message import Messages
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    reports: list[str] = []

    async def report(message: str) -> None:
        reports.append(message)

    pipeline = MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="test-progress",
        progress_reporter=report,
    )

    await pipeline.report_progress("我会把你的需求转换成系统内命令，确认参数后调用现有功能返回结果。", stage="route")
    await pipeline.report_progress("我会把你的需求转换成系统内命令，确认参数后调用现有功能返回结果。", stage="route")
    await pipeline.report_progress("", stage="extract")
    await pipeline.report_progress("我会先检索相关资料，把命中的内容压缩成可用上下文后再回答。", stage="rag")

    assert reports == ["我会先检索相关资料，把命中的内容压缩成可用上下文后再回答。"]


@pytest.mark.asyncio
async def test_extract_node_keeps_internal_progress_hidden(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.llm.message import Context, LLMRole, Messages
    from src.core.agent.runtime import pipeline as pipeline_module

    reports: list[str] = []

    async def report(message: str) -> None:
        reports.append(message)

    async def fake_execute(self, messages):
        return Context(role=LLMRole.user, content=[])

    monkeypatch.setattr(pipeline_module.ExtractAgent, "execute", fake_execute)

    pipeline = pipeline_module.MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="extract-progress",
        progress_reporter=report,
    )
    state = pipeline_module.PipelineState(trace_id="extract-progress")

    await pipeline_module.ExtractContextNode().run(pipeline, state)

    assert state.extracted_context is not None
    assert reports == []


def test_normalize_auto_task_reply_builds_fallback_for_commands(loaded_plugins):
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.schema import AutoTask, AgentPlan, IntentRoute, AutoTaskList

    reply = MessageProcessingPipeline.normalize_auto_task_reply(
        IntentRoute(intent="command", requires_command=True),
        AgentPlan(goal="查询我的身份", requires_command=True, should_execute=True),
        AutoTaskList(tasks=[AutoTask(command="我的信息", params=[])]),
    )

    assert "调用“我的信息”" in reply


def test_normalize_auto_task_reply_builds_fallback_for_confirmation(loaded_plugins):
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.schema import AgentPlan, IntentRoute, AutoTaskList

    reply = MessageProcessingPipeline.normalize_auto_task_reply(
        IntentRoute(intent="command", requires_command=True, need_confirm=True),
        AgentPlan(missing_info=["班级名称", "通知内容"]),
        AutoTaskList(need_confirm=True),
    )

    assert "班级名称、通知内容" in reply
