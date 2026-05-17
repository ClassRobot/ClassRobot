from types import SimpleNamespace

import pytest

from tests.autogpt.test_local_context_query import build_helpers_with_local_queries


def build_observability_helpers():
    """构造观测测试使用的最小命令目录。"""

    from tests.autogpt.command_tool_helpers import ensure_service_helper

    helpers = build_helpers_with_local_queries()
    helpers.append(ensure_service_helper("创建通知", "给班级创建一条通知", risk_level="high"))
    return helpers


@pytest.mark.asyncio
async def test_route_stage_observability_records_prompt_length_and_recall(loaded_plugins, monkeypatch):
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.schema import ChatMessage

    async def fake_client_create(*args, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"intent":"chat","reply":"好的","requires_rag":false,"requires_command":false,"need_confirm":false,"reason":"普通闲聊"}'
                    )
                )
            ]
        )

    monkeypatch.setattr(pipeline_module, "client_create", fake_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_observability_helpers(),
        Messages(),
        trace_id="obs-route",
    )
    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="帮我发一个班级通知")]))

    route_metric = next(metric for metric in result.observability.prompt_stages if metric.stage == "route")
    assert route_metric.prompt_char_length > 0
    assert route_metric.recalled_command_count == len(route_metric.recalled_commands)
    assert "创建通知" in route_metric.recalled_commands
    assert result.observability.final_hit_commands == []


@pytest.mark.asyncio
async def test_local_query_observability_records_final_hit_commands(loaded_plugins, monkeypatch):
    from core.llm.message import Content, Messages
    from core.agent.runtime import pipeline as pipeline_module
    from core.agent.runtime.schema import ChatMessage

    async def fail_client_create(*args, **kwargs):
        raise AssertionError("local context queries should not require LLM planning")

    monkeypatch.setattr(pipeline_module, "client_create", fail_client_create)

    pipeline = pipeline_module.MessageProcessingPipeline(
        build_helpers_with_local_queries(),
        Messages(),
        trace_id="obs-local-query",
    )
    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="我明天有什么课")]))

    assert result.observability.final_hit_commands == ["查询课表"]
    assert result.workflow is not None
    assert result.workflow.observability.final_hit_commands == ["查询课表"]


@pytest.mark.asyncio
async def test_workflow_executor_observability_detects_repeated_invocation(loaded_plugins):
    from core.agent.runtime.workflow import WorkflowExecutor
    from core.agent.runtime.schema import WorkflowStep, TaskWorkflow, CommandObservation

    async def dispatch(task):
        return [
            CommandObservation(
                trace_id="obs-repeat",
                command=task.command,
                success=True,
                message="命令已通过统一执行器完成。",
            )
        ]

    workflow = TaskWorkflow(
        trace_id="obs-repeat",
        kind="command_sequence",
        steps=[
            WorkflowStep(step_id="step-1", title="执行命令：查询课表", command="查询课表"),
            WorkflowStep(step_id="step-2", title="执行命令：查询课表", command="查询课表"),
        ],
    )

    execution = await WorkflowExecutor(dispatch).execute(workflow)

    assert execution.observability is not None
    assert execution.observability.execution.executed_commands == ["查询课表", "查询课表"]
    assert execution.observability.execution.repeated_invocation is True
    assert execution.observability.execution.repeated_commands == ["查询课表"]
