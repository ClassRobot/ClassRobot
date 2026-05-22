import pytest

from tests.autogpt.eval_cases import ARG_EVAL_CASES, EvalGateReport, ROUTE_EVAL_CASES, TOOL_EVAL_CASES
from tests.autogpt.semantic_helpers import (
    task_response,
    plan_response,
    route_response,
    extract_response,
    patch_pipeline_llm,
    build_helpers_with_semantic_commands,
)


def build_eval_helpers():
    """构造 route/tool/arg 门禁共用的命令目录。"""

    from tests.autogpt.command_tool_helpers import ensure_service_helper

    helpers = build_helpers_with_semantic_commands()
    helpers.append(ensure_service_helper("创建通知", "给班级创建一条通知", risk_level="high"))
    return helpers


def assert_eval_report(report: EvalGateReport) -> None:
    """断言某类评测样例全部通过。"""

    assert (
        report.passed == report.total
    ), f"{report.category} 评测未全部通过: {report.passed}/{report.total}\n" + "\n".join(
        f"- {failure}" for failure in report.failures
    )


@pytest.mark.asyncio
async def test_route_eval_gate(loaded_plugins, monkeypatch):
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.schema import ChatMessage

    report = EvalGateReport(category="route")

    for case in ROUTE_EVAL_CASES:
        patch_pipeline_llm(
            monkeypatch,
            [
                route_response(),
                extract_response(case.query),
                plan_response(case.expected_command, case.query),
                task_response(case.expected_command, f"我会调用{case.expected_command}处理。"),
            ],
        )
        pipeline = MessageProcessingPipeline(
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
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.llm.message import Content, Messages

    pipeline = MessageProcessingPipeline(
        build_eval_helpers(),
        Messages(),
        trace_id="eval-tool-catalog-visibility",
    )
    selected = pipeline.select_route_command_tools([Content(type="text", value="没有任何关键词命中的请求")])
    selected_commands = {tool.command for tool in selected}
    report = EvalGateReport(category="tool")

    for case in TOOL_EVAL_CASES:
        passed = case.expected_command in selected_commands
        report.record(case.name, passed, detail=f"visible={sorted(selected_commands)}")

    assert_eval_report(report)


@pytest.mark.asyncio
async def test_arg_eval_gate(loaded_plugins, monkeypatch):
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.schema import ChatMessage

    report = EvalGateReport(category="arg")

    for case in ARG_EVAL_CASES:
        patch_pipeline_llm(
            monkeypatch,
            [
                route_response(),
                extract_response(case.query),
                plan_response(case.expected_command, case.query),
                task_response(case.expected_command, f"我会调用{case.expected_command}处理。", case.expected_params),
            ],
        )
        pipeline = MessageProcessingPipeline(
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
