from __future__ import annotations

import pytest


def test_agent_catalog_exposes_default_specialized_agents(loaded_plugins):
    from src.core.agent.runtime.delegation import AgentCatalog

    _ = loaded_plugins
    catalog = AgentCatalog.default()
    names = {agent.name for agent in catalog.agents}

    assert {
        "workflow_supervisor",
        "conversation_agent",
        "knowledge_agent",
        "realtime_lookup_agent",
        "execution_agent",
        "reply_synthesis_agent",
    }.issubset(names)
    assert catalog.get("execution_agent").allow_delegate is False
    assert "mcp_tool" in catalog.get("realtime_lookup_agent").allowed_tool_sources


def test_action_result_converts_to_tool_observation(loaded_plugins):
    from src.core.agent.runtime.execution import ActionResult, ActionRequest

    _ = loaded_plugins
    request = ActionRequest(
        trace_id="host-action",
        source_type="mcp_tool",
        tool_name="browser_search",
        user_goal="查询热点",
        query="今日中文互联网热点",
    )
    observation = ActionResult(
        request=request,
        display_summary="检索到了三条中文热点摘要。",
        context_summary="中文热点：科技、教育、文娱。",
        raw_result={"items": 3},
    ).to_observation()

    assert observation.trace_id == "host-action"
    assert observation.source_type == "mcp_tool"
    assert observation.tool_name == "browser_search"
    assert observation.query == "今日中文互联网热点"
    assert observation.outputs_sent_to_user is False
    assert observation.context_summary == "中文热点：科技、教育、文娱。"


@pytest.mark.asyncio
async def test_chat_session_builds_host_turn_artifacts(monkeypatch, loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import IntentRoute, AutoTaskList, TaskWorkflow, AgentTurnResult

    _ = loaded_plugins

    async def fake_process(self, message):
        return AgentTurnResult(
            route=IntentRoute(intent="chat", reason="普通问候"),
            auto_tasks=AutoTaskList(reply="你好，我在。", tasks=[], need_confirm=False),
            workflow=TaskWorkflow(kind="chat", status="planned", steps=[]),
        )

    monkeypatch.setattr("src.core.agent.runtime.util.MessageProcessingPipeline.process", fake_process)

    session = ChatSession(user_id=1, helpers=Helpers())
    result = await session.send_message("你好")

    assert result.auto_tasks.reply == "你好，我在。"
    assert session.last_turn_envelope is not None
    assert session.last_turn_envelope.message_preview == "你好"
    assert session.last_context_pack is not None
    assert session.last_context_pack.turn_context["user_id"] == 1
    assert session.last_turn_output_bundle is not None
    assert session.last_turn_output_bundle.decision.decision_type == "direct_reply"
    assert session.user_visible_initial_reply(result) == "你好，我在。"
    assert any("# 系统最终回复记录" in message.single_modal() for message in session.messages.messages)
    assert {record.target_agent for record in session.last_handoff_records} >= {
        "workflow_supervisor",
        "conversation_agent",
        "reply_synthesis_agent",
    }


@pytest.mark.asyncio
async def test_host_marks_executable_workflow_for_execution(monkeypatch, loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import IntentRoute, AutoTaskList, TaskWorkflow, WorkflowStep, AgentTurnResult

    _ = loaded_plugins

    async def fake_process(self, message):
        workflow = TaskWorkflow(
            kind="command",
            status="planned",
            goal="查询我的信息",
            steps=[WorkflowStep(step_id="step-1", title="执行命令", command="我的信息")],
        )
        return AgentTurnResult(
            route=IntentRoute(intent="command", requires_command=True, reason="需要命令"),
            auto_tasks=AutoTaskList(reply="我会查询你的信息。", tasks=[], need_confirm=False),
            workflow=workflow,
        )

    monkeypatch.setattr("src.core.agent.runtime.util.MessageProcessingPipeline.process", fake_process)

    session = ChatSession(user_id=1, helpers=Helpers())
    turn_result = await session.send_message("我是什么身份")

    assert session.last_turn_output_bundle is not None
    assert session.last_turn_output_bundle.decision.decision_type == "execute"
    assert session.last_turn_output_bundle.decision.requires_execution is True
    assert session.last_turn_output_bundle.reply.messages[0].message_type == "progress_message"
    assert "execution_agent" in {record.target_agent for record in session.last_handoff_records}
    assert turn_result.workflow is not None
    assert turn_result.workflow.observability.handoffs


@pytest.mark.asyncio
async def test_host_rewrites_action_claim_when_no_workflow_step(monkeypatch, loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.util import ChatSession
    from src.core.agent.runtime.schema import IntentRoute, AutoTaskList, TaskWorkflow, AgentTurnResult

    _ = loaded_plugins

    async def fake_process(self, message):
        return AgentTurnResult(
            route=IntentRoute(intent="complex_task", reason="模型声称会查但没有步骤"),
            auto_tasks=AutoTaskList(reply="我现在查一下，马上告诉你。", tasks=[], need_confirm=False),
            workflow=TaskWorkflow(kind="chat", status="planned", steps=[]),
        )

    monkeypatch.setattr("src.core.agent.runtime.util.MessageProcessingPipeline.process", fake_process)

    session = ChatSession(user_id=1, helpers=Helpers())
    result = await session.send_message("最近热点")

    assert "不会假装已经开始查询" in session.user_visible_initial_reply(result)
    assert "不会假装已经开始查询" in (result.auto_tasks.reply or "")
    assert session.last_turn_output_bundle is not None
    assert session.last_turn_output_bundle.reply.failure_reason == "action_claim_without_workflow"


def test_context_engine_extracts_reply_and_observation_memory(loaded_plugins):
    from src.core.llm.message import Messages
    from src.core.agent.runtime.context import ContextEngine

    _ = loaded_plugins
    messages = Messages()
    messages.assistant_message(
        '# 系统最终回复记录\ntrace_id: t1\n{"trace_id":"t1","reply":"第五条没有可靠来源",'
        '"summary":"第五条没有可靠来源","source_observations":["browser_search"],"language":"zh-CN"}'
    )
    messages.assistant_message(
        '# 系统命令执行观察\ntrace_id: t1\n[{"source_type":"mcp_tool","tool_name":"browser_search",'
        '"status":"succeeded","relevance":"medium","answer_quality":"partial","context_summary":"热点摘要"}]'
    )

    pack = ContextEngine().build_pack(
        trace_id="t2",
        user_id=1,
        message_preview="第五条是什么",
        messages=messages,
    )

    assert pack.session_context["recent_final_replies"][0]["summary"] == "第五条没有可靠来源"
    assert pack.tool_state_context["recent_observations"][0]["tool_name"] == "browser_search"
