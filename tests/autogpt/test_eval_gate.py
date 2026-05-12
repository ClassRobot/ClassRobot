import pytest

from tests.autogpt.eval_cases import ARG_EVAL_CASES, EvalGateReport, ROUTE_EVAL_CASES, TOOL_EVAL_CASES
from tests.autogpt.test_local_context_query import build_helpers_with_local_queries


def build_eval_helpers():
    """构造 route/tool/arg 门禁共用的命令目录。"""

    from utils.helper import Helper

    helpers = build_helpers_with_local_queries()
    helpers.append(Helper(command="创建通知", description="给班级创建一条通知"))
    return helpers


def assert_eval_report(report: EvalGateReport) -> None:
    """断言某类评测样例全部通过。"""

    assert report.passed == report.total, (
        f"{report.category} 评测未全部通过: {report.passed}/{report.total}\n"
        + "\n".join(f"- {failure}" for failure in report.failures)
    )


@pytest.mark.asyncio
async def test_route_eval_gate(loaded_plugins, monkeypatch):
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module
    from src.plugins.autogpt.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("route eval gate should stay on deterministic local routing")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)
    report = EvalGateReport(category="route")

    for case in ROUTE_EVAL_CASES:
        pipeline = pipeline_module.MessageProcessingPipeline(
            build_eval_helpers(),
            Messages(),
            trace_id=f"eval-route-{case.name}",
        )
        result = await pipeline.process(ChatMessage(message=[Content(type="text", value=case.query)]))
        actual_commands = [task.command for task in (result.auto_tasks.tasks if result.auto_tasks else [])]
        passed = (
            result.route is not None
            and result.route.intent == case.expected_intent
            and actual_commands == [case.expected_command]
            and result.observability.final_hit_commands == [case.expected_command]
        )
        report.record(
            case.name,
            passed,
            detail=(
                f"intent={result.route.intent if result.route else None}, "
                f"commands={actual_commands}, "
                f"final_hit={result.observability.final_hit_commands}"
            ),
        )

    assert_eval_report(report)


def test_tool_eval_gate(loaded_plugins):
    from src.plugins.autogpt.command_tools import CommandToolCatalog

    catalog = CommandToolCatalog.from_helpers(build_eval_helpers())
    report = EvalGateReport(category="tool")

    for case in TOOL_EVAL_CASES:
        selected = catalog.select_tools(query=case.query, limit=case.limit)
        selected_commands = [tool.command for tool in selected]
        passed = bool(selected_commands) and selected_commands[0] == case.expected_command
        report.record(case.name, passed, detail=f"selected={selected_commands}")

    assert_eval_report(report)


@pytest.mark.asyncio
async def test_arg_eval_gate(loaded_plugins, monkeypatch):
    from utils.llm.message import Content, Messages
    from src.plugins.autogpt import pipeline as pipeline_module
    from src.plugins.autogpt.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("arg eval gate should stay on deterministic local routing")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)
    report = EvalGateReport(category="arg")

    for case in ARG_EVAL_CASES:
        pipeline = pipeline_module.MessageProcessingPipeline(
            build_eval_helpers(),
            Messages(),
            trace_id=f"eval-arg-{case.name}",
        )
        result = await pipeline.process(ChatMessage(message=[Content(type="text", value=case.query)]))
        tasks = result.auto_tasks.tasks if result.auto_tasks else []
        command = tasks[0].command if tasks else None
        params = [param.value for param in tasks[0].params] if tasks else []
        passed = command == case.expected_command and params == case.expected_params
        report.record(case.name, passed, detail=f"command={command}, params={params}")

    assert_eval_report(report)
