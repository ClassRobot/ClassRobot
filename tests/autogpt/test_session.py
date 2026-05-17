import json
import pytest


def test_record_observations_writes_traceable_context(loaded_plugins):
    from utils.helper import Helpers
    from core.agent.runtime.util import ChatSession
    from core.agent.runtime.schema import CommandObservation, Param

    session = ChatSession(user_id=1, helpers=Helpers())
    session.last_trace_id = "autogpt-test"

    session.record_observations(
        [
            CommandObservation(
                trace_id="autogpt-test",
                command="查询课表",
                params=[Param(type="text", value="今天")],
                success=True,
                message="命令已通过统一执行器完成。",
                outputs=["今天上午第一节是高等数学。"],
            )
        ]
    )

    messages = session.messages.messages
    assert len(messages) == 2
    content = messages[0].single_modal()
    assert content.startswith("# 系统命令执行观察\ntrace_id: autogpt-test\n")

    payload = json.loads(content.split("\n", 2)[2])
    assert payload[0]["trace_id"] == "autogpt-test"
    assert payload[0]["command"] == "查询课表"
    assert payload[0]["success"] is True
    assert payload[0]["outputs"] == ["今天上午第一节是高等数学。"]

    output_context = messages[1].single_modal()
    assert output_context.startswith("# 系统命令返回结果\ntrace_id: autogpt-test\n")
    assert "命令：查询课表" in output_context
    assert "今天上午第一节是高等数学。" in output_context


def test_record_observations_prefers_context_outputs_for_agent_context(loaded_plugins):
    from utils.helper import Helpers
    from core.agent.runtime.util import ChatSession
    from core.agent.runtime.schema import CommandObservation

    session = ChatSession(user_id=1, helpers=Helpers())
    session.last_trace_id = "autogpt-context-output"

    session.record_observations(
        [
            CommandObservation(
                trace_id="autogpt-context-output",
                command="我的信息",
                success=True,
                message="命令已通过统一执行器完成。",
                outputs=["用户信息：昵称是小王，角色是教师。"],
                context_outputs=["当前用户昵称小王，已绑定教师身份。"],
                outputs_sent_to_user=False,
            )
        ]
    )

    output_context = session.messages.messages[-1].single_modal()
    assert "当前用户昵称小王，已绑定教师身份。" in output_context
    assert "用户信息：昵称是小王，角色是教师。" not in output_context


@pytest.mark.asyncio
async def test_record_workflow_writes_traceable_context(loaded_plugins):
    from utils.helper import Helpers
    from core.agent.runtime.util import ChatSession
    from core.agent.runtime.schema import TaskWorkflow, WorkflowStep

    session = ChatSession(user_id=1, helpers=Helpers())
    workflow = TaskWorkflow(
        trace_id="autogpt-workflow",
        kind="command",
        goal="查询课表",
        steps=[WorkflowStep(step_id="step-1", title="执行命令：查询课表", command="查询课表")],
    )

    await session.record_workflow(workflow)

    messages = session.messages.messages
    assert len(messages) == 1
    content = messages[0].single_modal()
    assert content.startswith("# 系统工作流状态\ntrace_id: autogpt-workflow\n")

    payload = json.loads(content.split("\n", 2)[2])
    assert payload["trace_id"] == "autogpt-workflow"
    assert payload["steps"][0]["command"] == "查询课表"


@pytest.mark.asyncio
async def test_execute_task_workflow_generates_final_reply_from_observations(monkeypatch, loaded_plugins):
    from utils.helper import Helpers
    from core.agent.runtime.util import ChatSession
    from core.agent.runtime.schema import TaskWorkflow, WorkflowStep, CommandObservation

    session = ChatSession(user_id=1, helpers=Helpers())
    session.last_trace_id = "autogpt-final-reply"
    workflow = TaskWorkflow(
        trace_id="autogpt-final-reply",
        kind="command",
        goal="查询我的信息",
        steps=[WorkflowStep(step_id="step-1", title="执行命令：我的信息", command="我的信息")],
    )

    async def dispatch(task):
        return [
            CommandObservation(
                trace_id="autogpt-final-reply",
                command=task.command,
                success=True,
                message="命令已通过统一执行器完成。",
                outputs=["用户信息：你是教师用户。"],
                context_outputs=["当前用户已绑定教师身份。"],
                outputs_sent_to_user=False,
            )
        ]

    async def fake_final_reply(execution):
        return "你当前已经绑定教师身份。"

    monkeypatch.setattr(session, "build_execution_final_reply", fake_final_reply)

    execution = await session.execute_task_workflow(workflow, dispatch)

    assert execution.raw_outputs == ["用户信息：你是教师用户。"]
    assert execution.final_reply == "你当前已经绑定教师身份。"
    assert any("# 系统命令返回结果" in message.single_modal() for message in session.messages.messages)
