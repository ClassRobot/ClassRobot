import json
import asyncio
from types import SimpleNamespace

import pytest


def test_record_observations_writes_traceable_context(loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import Param, CommandObservation

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
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import CommandObservation

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
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep

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
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep, CommandObservation

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
    assert any("# 系统最终回复记录" in message.single_modal() for message in session.messages.messages)
    assert session.messages.messages[-1].single_modal() == "你当前已经绑定教师身份。"


@pytest.mark.asyncio
async def test_execute_task_workflow_falls_back_when_reply_synthesis_times_out(monkeypatch, loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep, CommandObservation

    session = ChatSession(user_id=1, helpers=Helpers())
    session.last_trace_id = "autogpt-final-timeout"
    workflow = TaskWorkflow(
        trace_id="autogpt-final-timeout",
        kind="command",
        goal="查询外部资料",
        steps=[WorkflowStep(step_id="step-1", title="调用 MCP 工具", command="browser_search", step_type="mcp_tool")],
    )

    async def dispatch(task):
        raise AssertionError("this workflow should not dispatch project commands")

    async def fake_execute(self, workflow):
        from src.core.agent.runtime.schema import WorkflowExecutionResult

        return WorkflowExecutionResult(
            workflow=workflow,
            observations=[
                CommandObservation(
                    trace_id="autogpt-final-timeout",
                    command="browser_search",
                    dispatch_type="mcp_tool",
                    success=True,
                    message="检索完成。",
                    outputs=["热点摘要结果"],
                    context_outputs=["热点摘要结果"],
                    outputs_sent_to_user=False,
                )
            ],
            raw_outputs=["热点摘要结果"],
            user_message="热点摘要结果",
        )

    async def slow_final_reply(execution):
        await asyncio.sleep(0.05)
        return "不应该等到这里"

    async def fast_timeout(execution):
        try:
            return await asyncio.wait_for(slow_final_reply(execution), timeout=0.01)
        except asyncio.TimeoutError:
            return execution.user_message or ""

    monkeypatch.setattr("src.core.agent.runtime.util.CognitiveAgentLoop.execute", fake_execute)
    monkeypatch.setattr(session, "build_execution_final_reply_with_timeout", fast_timeout)

    execution = await session.execute_task_workflow(workflow, dispatch)

    assert execution.final_reply == "热点摘要结果"


@pytest.mark.asyncio
async def test_execution_reply_timeout_does_not_leak_full_raw_output(monkeypatch, loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep, CommandObservation

    session = ChatSession(user_id=1, helpers=Helpers())
    session.last_trace_id = "autogpt-no-raw-leak"
    workflow = TaskWorkflow(
        trace_id="autogpt-no-raw-leak",
        kind="command",
        goal="查询最近网上热点",
        steps=[WorkflowStep(step_id="step-1", title="调用 MCP 工具", command="browser_search", step_type="mcp_tool")],
    )
    raw_output = "https://example.com/" + "very-long-url-" * 80

    async def dispatch(task):
        raise AssertionError("this workflow should not dispatch project commands")

    async def fake_execute(self, workflow):
        from src.core.agent.runtime.schema import WorkflowExecutionResult

        return WorkflowExecutionResult(
            workflow=workflow,
            observations=[
                CommandObservation(
                    trace_id="autogpt-no-raw-leak",
                    command="browser_search",
                    source_type="mcp_tool",
                    tool_name="browser_search",
                    dispatch_type="mcp_tool",
                    success=True,
                    message="检索完成。",
                    display_summary="工具返回内容与问题不匹配，无法可靠回答。",
                    context_summary="低相关搜索结果。",
                    outputs=[raw_output],
                    context_outputs=["低相关搜索结果。"],
                    raw_result={"raw": raw_output},
                    outputs_sent_to_user=False,
                    relevance="low",
                    answer_quality="insufficient",
                    next_actions=["retry_search"],
                )
            ],
            raw_outputs=[raw_output],
            user_message=raw_output,
        )

    async def fake_timeout(execution):
        from src.core.agent.runtime.observation_quality import build_safe_execution_fallback

        return build_safe_execution_fallback(execution.observations)

    monkeypatch.setattr("src.core.agent.runtime.util.CognitiveAgentLoop.execute", fake_execute)
    monkeypatch.setattr(session, "build_execution_final_reply_with_timeout", fake_timeout)

    execution = await session.execute_task_workflow(workflow, dispatch)

    assert "http" not in execution.final_reply
    assert "不匹配" in execution.final_reply or "不能可靠回答" in execution.final_reply


@pytest.mark.asyncio
async def test_plugin_skips_empty_workflow_execution(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    import src.plugins.application.active.autogpt as plugin_module
    from src.core.agent.runtime.schema import AutoTaskList, TaskWorkflow, AgentTurnResult

    sent_messages: list[str] = []

    class FakeMatcher:
        async def send(self, message):
            sent_messages.append(str(message))

        async def finish(self, message):
            raise AssertionError(f"finish should not be called: {message}")

    class FakeTarget:
        adapter = "test"
        private = True
        platform = "test"

    class FakeBot:
        pass

    class FakePlatform:
        platform = "qq.qq_api"
        platform_name = "qq"
        channel_id = None
        guild_id = None

    session = ChatSession(user_id=1, helpers=Helpers())
    session.last_trace_id = "autogpt-empty-workflow"
    session.helpers.active_roles = set()

    workflow = TaskWorkflow(
        trace_id="autogpt-empty-workflow",
        kind="chat",
        status="planned",
        steps=[],
    )
    turn_result = AgentTurnResult(
        auto_tasks=AutoTaskList(reply="这是直答结果。", tasks=[], need_confirm=False),
        workflow=workflow,
    )

    async def fake_send_message(*args, **kwargs):
        return turn_result

    async def fake_execute_task_workflow(*args, **kwargs):
        raise AssertionError("empty workflow should not be executed")

    class FakeRenderedMessage:
        def __init__(self, text: str) -> None:
            self.text = text

        async def export(self, **kwargs):
            return self.text

    def fake_markdown_to_message(text: str):
        return FakeRenderedMessage(text)

    monkeypatch.setattr(session, "send_message", fake_send_message)
    monkeypatch.setattr(session, "execute_task_workflow", fake_execute_task_workflow)
    monkeypatch.setattr(plugin_module, "markdown_to_message", fake_markdown_to_message)

    await plugin_module._(
        bot=FakeBot(),
        event=SimpleNamespace(message_id="1"),
        matcher=FakeMatcher(),
        message="你查了吗",
        target=FakeTarget(),
        platform=FakePlatform(),
        chat_session=session,
    )

    assert sent_messages == ["这是直答结果。"]
