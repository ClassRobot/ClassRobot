import pytest


@pytest.mark.parametrize(
    ("intent", "requires_rag", "requires_command", "expected"),
    [
        ("chat", False, False, ""),
        ("violation", False, False, ""),
        ("vision_file", False, False, "我先看一下图片或文件内容，请稍等~"),
        ("knowledge", True, False, "我查一下相关资料，请稍等~"),
        ("command", False, True, "我帮你处理一下，请稍等~"),
        ("complex_task", True, True, "我先查一下相关信息，再帮你处理，请稍等~"),
    ],
)
def test_build_user_progress_message(loaded_plugins, intent, requires_rag, requires_command, expected):
    from src.plugins.autogpt.schema import IntentRoute
    from src.plugins.autogpt.pipeline import MessageProcessingPipeline

    route = IntentRoute(
        intent=intent,
        requires_rag=requires_rag,
        requires_command=requires_command,
    )

    assert MessageProcessingPipeline.build_user_progress_message(route) == expected


@pytest.mark.asyncio
async def test_report_progress_deduplicates_messages(loaded_plugins):
    from utils.helper import Helpers
    from utils.llm.message import Messages
    from src.plugins.autogpt.pipeline import MessageProcessingPipeline

    reports: list[str] = []

    async def report(message: str) -> None:
        reports.append(message)

    pipeline = MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="test-progress",
        progress_reporter=report,
    )

    await pipeline.report_progress("我帮你处理一下，请稍等~")
    await pipeline.report_progress("我帮你处理一下，请稍等~")
    await pipeline.report_progress("")
    await pipeline.report_progress("我查一下相关资料，请稍等~")

    assert reports == ["我帮你处理一下，请稍等~", "我查一下相关资料，请稍等~"]
