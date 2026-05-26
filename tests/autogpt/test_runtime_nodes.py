from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_planner_node_includes_user_message_for_plan_request(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.schema import IntentRoute
    from src.core.agent.runtime.coordination.nodes import PlannerNode
    from src.core.agent.runtime.coordination.state import PipelineState
    from src.core.llm.message import Content, Context, LLMRole, Messages
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    pipeline = MessageProcessingPipeline(Helpers(), Messages(), trace_id="planner-user-message")
    captured: dict[str, object] = {}

    async def fake_ensure_mcp_tools() -> None:
        return None

    async def fake_create_llm_completion(messages: Messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"goal":"查询班级","requires_command":true,"should_execute":true,'
                            '"candidate_commands":["查询班级"],"steps":["查询班级"],"reason":"测试"}'
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(pipeline, "ensure_mcp_tools", fake_ensure_mcp_tools)
    monkeypatch.setattr(pipeline, "create_llm_completion", fake_create_llm_completion)

    state = PipelineState(
        trace_id="planner-user-message",
        user_content=[Content(type="text", value="我在哪个班级")],
        intent_route=IntentRoute(intent="command", requires_command=True),
        extracted_context=Context(role=LLMRole.user, content="我在哪个班级"),
    )

    await PlannerNode().run(pipeline, state)

    sent_messages = captured["messages"]
    assert isinstance(sent_messages, Messages)
    assert any(
        isinstance(message, Context) and message.role == LLMRole.user and message.single_modal() == "我在哪个班级"
        for message in sent_messages
    )
    assert state.agent_plan is not None
    assert state.agent_plan.goal == "查询班级"


@pytest.mark.asyncio
async def test_route_node_explains_missing_realtime_external_capability(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.coordination.state import PipelineState
    from src.core.agent.runtime.coordination.nodes import IntentRouteNode
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    reports: list[str] = []

    async def report(message: str) -> None:
        reports.append(message)

    pipeline = MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="route-missing-realtime",
        progress_reporter=report,
    )

    async def fake_ensure_mcp_tools() -> None:
        return None

    async def fake_create_llm_completion(messages: Messages, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"intent":"knowledge","reply":null,"requires_rag":false,'
                            '"requires_command":false,"need_confirm":false,'
                            '"reason":"用户需要最新公共外部信息",'
                            '"knowledge_sources":[],'
                            '"capability_requirements":[{"kind":"mcp_tool","freshness":"realtime",'
                            '"scope":"public_external","execution_mode":"retrieve","required":true,'
                            '"reason":"需要查询最新新闻"}],"unavailable_reason":null}'
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(pipeline, "ensure_mcp_tools", fake_ensure_mcp_tools)
    monkeypatch.setattr(pipeline, "create_llm_completion", fake_create_llm_completion)

    state = PipelineState(
        trace_id="route-missing-realtime",
        user_content=[Content(type="text", value="最近有什么新闻吗")],
    )

    await IntentRouteNode().run(pipeline, state)

    assert state.intent_route is not None
    assert state.intent_route.unavailable_reason == "realtime_source_missing"
    assert state.auto_tasks is not None
    assert state.auto_tasks.tasks == []
    assert "实时新闻或网页检索工具" in (state.auto_tasks.reply or "")
    assert reports == []


@pytest.mark.asyncio
async def test_route_node_uses_direct_reply_instead_of_generic_router_reply(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.coordination.state import PipelineState
    from src.core.agent.runtime.coordination.nodes import IntentRouteNode
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    pipeline = MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="route-direct-chat-reply",
    )

    async def fake_ensure_mcp_tools() -> None:
        return None

    calls: list[Messages] = []

    async def fake_create_llm_completion(messages: Messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=(
                                '{"intent":"chat","reply":"我在，有什么需要我帮你处理的吗？",'
                                '"requires_rag":false,"requires_command":false,"need_confirm":false,'
                                '"reason":"错误地把实时问题当普通聊天",'
                                '"knowledge_sources":[],"capability_requirements":[],"unavailable_reason":null}'
                            )
                        )
                    )
                ]
            )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="我目前没有可用的实时新闻或网页检索能力，所以不能可靠告诉你最近网上的热点。"))]
        )

    monkeypatch.setattr(pipeline, "ensure_mcp_tools", fake_ensure_mcp_tools)
    monkeypatch.setattr(pipeline, "create_llm_completion", fake_create_llm_completion)

    state = PipelineState(
        trace_id="route-direct-chat-reply",
        user_content=[Content(type="text", value="我想问最近网上有什么热点吗")],
    )

    await IntentRouteNode().run(pipeline, state)

    assert len(calls) == 2
    assert state.auto_tasks is not None
    assert "实时新闻或网页检索能力" in (state.auto_tasks.reply or "")
    assert "我在，有什么需要" not in (state.auto_tasks.reply or "")


@pytest.mark.asyncio
async def test_route_node_does_not_short_circuit_complex_task_that_needs_mcp(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.coordination.state import PipelineState
    from src.core.agent.runtime.coordination.nodes import IntentRouteNode
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    pipeline = MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="route-complex-task-mcp",
    )

    calls: list[Messages] = []

    async def fake_ensure_mcp_tools() -> None:
        return None

    async def fake_create_llm_completion(messages: Messages, **kwargs):
        calls.append(messages)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"intent":"complex_task","reply":null,"requires_rag":false,'
                            '"requires_command":false,"need_confirm":false,'
                            '"reason":"需要调用实时公共外部检索能力",'
                            '"knowledge_sources":[],"capability_requirements":[{"kind":"mcp_tool",'
                            '"freshness":"realtime","scope":"public_external",'
                            '"execution_mode":"retrieve","required":true,'
                            '"reason":"需要联网查询公开信息"}],"unavailable_reason":null}'
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(pipeline, "ensure_mcp_tools", fake_ensure_mcp_tools)
    monkeypatch.setattr(pipeline, "create_llm_completion", fake_create_llm_completion)
    monkeypatch.setattr(pipeline, "has_realtime_external_lookup", lambda: True)

    state = PipelineState(
        trace_id="route-complex-task-mcp",
        user_content=[Content(type="text", value="你查一下最近网上热点")],
    )

    await IntentRouteNode().run(pipeline, state)

    assert state.intent_route is not None
    assert state.intent_route.intent == "complex_task"
    assert state.auto_tasks is None
    assert len(calls) == 1


def test_capability_catalog_exposes_realtime_mcp_as_first_class_capability(loaded_plugins):
    from src.core.mcp.schema import MCPTool
    from src.platform.helper import Helpers
    from src.core.mcp.catalog import MCPToolCatalog
    from src.core.agent.runtime.harness.policy import PolicyHarness

    policy = PolicyHarness(helpers=Helpers())
    policy.mcp_tools = MCPToolCatalog(
        tools=[
            MCPTool(
                name="web_search",
                description="搜索最新网页和新闻",
                domain_tags=["web_search", "news"],
                freshness="realtime",
            )
        ],
        tool_index={
            "web_search": MCPTool(
                name="web_search",
                description="搜索最新网页和新闻",
                domain_tags=["web_search", "news"],
                freshness="realtime",
            )
        },
    )

    prompt = policy.render_capability_catalog_prompt()

    assert policy.has_realtime_external_lookup() is True
    assert "web_search [mcp_tool]" in prompt
    assert "has_realtime_external_lookup: true" in prompt


@pytest.mark.asyncio
async def test_pipeline_reuses_mcp_catalog_within_one_turn(loaded_plugins):
    from src.core.mcp.schema import MCPTool
    from src.platform.helper import Helpers
    from src.core.llm.message import Messages
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    calls = 0

    class FakeMCPClient:
        async def list_tools(self):
            nonlocal calls
            calls += 1
            return [
                MCPTool(
                    name="browser_search",
                    description="联网搜索公开信息",
                    domain_tags=["web_search", "news"],
                    freshness="realtime",
                    server_url="http://127.0.0.1:8000/mcp",
                )
            ]

    pipeline = MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="mcp-catalog-cache",
    )
    pipeline.policy.mcp_client = FakeMCPClient()

    await pipeline.ensure_mcp_tools()
    await pipeline.ensure_mcp_tools()
    await pipeline.ensure_mcp_tools()

    assert calls == 1
    assert pipeline.mcp_tools.get("browser_search") is not None


@pytest.mark.asyncio
async def test_planner_node_recovers_invalid_capability_requirements_for_realtime_mcp(loaded_plugins, monkeypatch):
    from src.core.mcp.schema import MCPTool
    from src.platform.helper import Helpers
    from src.core.mcp.catalog import MCPToolCatalog
    from src.core.agent.runtime.schema import IntentRoute
    from src.core.agent.runtime.coordination.nodes import PlannerNode
    from src.core.agent.runtime.coordination.state import PipelineState
    from src.core.llm.message import Content, Context, LLMRole, Messages
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    pipeline = MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="planner-invalid-capability-requirements",
    )
    pipeline.policy.mcp_tools = MCPToolCatalog(
        tools=[
            MCPTool(
                name="browser_search",
                description="联网搜索公开信息",
                domain_tags=["web_search", "news"],
                freshness="realtime",
                server_url="http://127.0.0.1:8000/mcp",
            )
        ],
        tool_index={
            "browser_search": MCPTool(
                name="browser_search",
                description="联网搜索公开信息",
                domain_tags=["web_search", "news"],
                freshness="realtime",
                server_url="http://127.0.0.1:8000/mcp",
            )
        },
    )
    pipeline.mcp_tools = pipeline.policy.mcp_tools

    async def fake_ensure_mcp_tools() -> None:
        return None

    async def fake_create_llm_completion(messages: Messages, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"goal":"查询最近网上热点","facts":[],"missing_info":[],"risk_level":"low",'
                            '"requires_rag":false,"requires_command":false,"should_execute":true,'
                            '"candidate_commands":[],"candidate_skills":[],"candidate_mcp_tools":[],'
                            '"capability_requirements":["mcp_tool","realtime","public_external"],'
                            '"steps":[],"confirmation_question":null,"reason":"需要联网查询"}'
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(pipeline, "ensure_mcp_tools", fake_ensure_mcp_tools)
    monkeypatch.setattr(pipeline, "create_llm_completion", fake_create_llm_completion)

    state = PipelineState(
        trace_id="planner-invalid-capability-requirements",
        user_content=[Content(type="text", value="最近网上有什么热点")],
        intent_route=IntentRoute.parse_obj(
            {
                "intent": "complex_task",
                "requires_command": False,
                "requires_rag": False,
                "capability_requirements": [
                    {
                        "kind": "mcp_tool",
                        "freshness": "realtime",
                        "scope": "public_external",
                        "execution_mode": "retrieve",
                        "required": True,
                        "reason": "需要联网查询公开信息",
                    }
                ],
            }
        ),
        extracted_context=Context(role=LLMRole.user, content="最近网上有什么热点"),
    )

    await PlannerNode().run(pipeline, state)

    assert state.agent_plan is not None
    assert state.agent_plan.candidate_mcp_tools == ["browser_search"]
    assert state.agent_plan.should_execute is True
    assert state.agent_plan.capability_requirements[0].kind == "mcp_tool"


@pytest.mark.asyncio
async def test_pipeline_blocks_quota_limited_model_for_rest_of_turn(loaded_plugins, monkeypatch):
    from src.platform.helper import Helpers
    from src.core.llm.message import Messages
    from src.core.agent.runtime import pipeline as pipeline_module
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    pipeline = MessageProcessingPipeline(
        Helpers(),
        Messages(),
        trace_id="llm-quota-block",
    )
    captured_kwargs: list[dict] = []
    error_snapshots = [
        [("gemini-3-flash-preview", "429 RESOURCE_EXHAUSTED quota exceeded")],
        [],
    ]

    async def fake_client_create(messages, **kwargs):
        captured_kwargs.append(dict(kwargs))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])

    monkeypatch.setattr(pipeline_module, "client_create", fake_client_create)
    monkeypatch.setattr(
        pipeline_module.llm_gateway,
        "get_last_attempt_errors",
        lambda: error_snapshots.pop(0) if error_snapshots else [],
    )
    monkeypatch.setattr(pipeline_module.llm_gateway, "clear_last_attempt_errors", lambda: None)

    await pipeline.create_llm_completion(Messages(), task_type=pipeline_module.LLMTaskType.plan)
    await pipeline.create_llm_completion(Messages(), task_type=pipeline_module.LLMTaskType.plan)

    assert "gemini-3-flash-preview" in pipeline.blocked_llm_names
    assert "gemini-3-flash-preview" in captured_kwargs[1]["exclude_llm_names"]


def test_agent_plan_supports_command_not_found(loaded_plugins):
    from src.core.agent.runtime.schema import AgentPlan

    payload = {
        "goal": "执行一些未知的命令",
        "facts": [],
        "missing_info": [],
        "risk_level": "low",
        "requires_rag": False,
        "requires_command": True,
        "should_execute": False,
        "candidate_commands": [],
        "candidate_skills": [],
        "candidate_mcp_tools": [],
        "capability_requirements": [],
        "unavailable_reason": "command_not_found",
        "steps": [],
        "confirmation_question": None,
        "reason": "未找到命令",
    }

    plan = AgentPlan.parse_obj(payload)
    assert plan.unavailable_reason == "command_not_found"
