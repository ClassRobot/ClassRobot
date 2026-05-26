import pytest

from tests.autogpt.semantic_helpers import (
    plan_response,
    task_response,
    route_response,
    extract_response,
    patch_pipeline_llm,
    build_helpers_with_semantic_commands,
)


@pytest.mark.asyncio
async def test_self_identity_query_uses_ai_route_and_plans_self_info(loaded_plugins, monkeypatch):
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.schema import ChatMessage
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    calls = patch_pipeline_llm(
        monkeypatch,
        [
            route_response(reason="用户询问自身权限，应调用账号信息命令。"),
            extract_response("我的身份是管理员吗"),
            plan_response("我的信息", "确认用户自身身份和权限"),
            task_response("我的信息", "我会先查询你的账号信息，再根据结果判断是否为管理员。"),
        ],
    )

    pipeline = MessageProcessingPipeline(
        build_helpers_with_semantic_commands(),
        Messages(),
        trace_id="semantic-self-identity",
    )
    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="我的身份是管理员吗")]))

    assert calls
    assert result.route is not None
    assert result.route.intent == "command"
    assert result.auto_tasks is not None
    assert [task.command for task in result.auto_tasks.tasks] == ["我的信息"]


@pytest.mark.asyncio
async def test_class_and_schedule_queries_are_planned_by_model_not_local_shortcuts(loaded_plugins, monkeypatch):
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.schema import ChatMessage
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    calls = patch_pipeline_llm(
        monkeypatch,
        [
            route_response(),
            extract_response("我有创建班级吗"),
            plan_response("查询班级", "查询用户创建或管理的班级"),
            task_response("查询班级", "我会查询你当前创建或管理的班级。"),
            route_response(),
            extract_response("我明天有什么课"),
            plan_response("查询课表", "查询用户明天的课表"),
            task_response("查询课表", "我会查询你明天的课表。", params=["1"]),
        ],
    )

    class_pipeline = MessageProcessingPipeline(
        build_helpers_with_semantic_commands(),
        Messages(),
        trace_id="semantic-class-query",
    )
    class_result = await class_pipeline.process(ChatMessage(message=[Content(type="text", value="我有创建班级吗")]))

    schedule_pipeline = MessageProcessingPipeline(
        build_helpers_with_semantic_commands(),
        Messages(),
        trace_id="semantic-schedule-query",
    )
    schedule_result = await schedule_pipeline.process(ChatMessage(message=[Content(type="text", value="我明天有什么课")]))

    assert len(calls) == 8
    assert class_result.auto_tasks is not None
    assert [task.command for task in class_result.auto_tasks.tasks] == ["查询班级"]
    assert schedule_result.auto_tasks is not None
    assert [task.command for task in schedule_result.auto_tasks.tasks] == ["查询课表"]
    assert [param.value for param in schedule_result.auto_tasks.tasks[0].params] == ["1"]


def test_route_and_plan_stage_expose_full_capability_catalog(loaded_plugins):
    from src.core.llm.message import Content, Context, LLMRole, Messages
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    pipeline = MessageProcessingPipeline(
        build_helpers_with_semantic_commands(),
        Messages(),
        trace_id="semantic-catalog-visibility",
    )
    route_tools = pipeline.select_route_command_tools([Content(type="text", value="完全不匹配的自然语言")])
    plan_tools = pipeline.select_plan_command_tools(Context(role=LLMRole.user, content="另一个不匹配的问题"))

    route_commands = {tool.command for tool in route_tools}
    plan_commands = {tool.command for tool in plan_tools}

    assert {"我的信息", "查询班级", "查询课表", "统计聊天记录"}.issubset(route_commands)
    assert {"我的信息", "查询班级", "查询课表", "统计聊天记录"}.issubset(plan_commands)


def test_default_graph_has_no_keyword_preroute_nodes(loaded_plugins):
    from src.core.agent.runtime.orchestration_config import default_graph_config
    from src.core.agent.runtime.node_registry import RUNTIME_NODE_REGISTRY, DEFAULT_RUNTIME_NODE_ORDER

    graph = default_graph_config()

    assert "local_context" not in RUNTIME_NODE_REGISTRY
    assert "local_chat_statistics" not in RUNTIME_NODE_REGISTRY
    assert "local_context" not in DEFAULT_RUNTIME_NODE_ORDER
    assert "local_chat_statistics" not in DEFAULT_RUNTIME_NODE_ORDER
    assert "local_context" not in graph.node_order
    assert "local_chat_statistics" not in graph.node_order
    assert ("append_user_message", "route") in {(edge.source, edge.target) for edge in graph.edges}


@pytest.mark.asyncio
async def test_realtime_hot_topic_query_generates_mcp_tool_task(loaded_plugins, monkeypatch):
    from src.core.mcp.schema import MCPTool
    from src.core.mcp.catalog import MCPToolCatalog
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.schema import ChatMessage
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    responses = [
        (
            '{"intent":"complex_task","reply":null,"requires_rag":false,"requires_command":false,'
            '"need_confirm":false,"reason":"需要调用实时公共外部检索能力","knowledge_sources":[],'
            '"capability_requirements":[{"kind":"mcp_tool","freshness":"realtime",'
            '"scope":"public_external","execution_mode":"retrieve","required":true,'
            '"reason":"需要联网查询公开信息"}],"unavailable_reason":null}'
        ),
        extract_response("最近网上有什么热点"),
        (
            '{"goal":"查询最近网上热点","facts":[],"missing_info":[],"risk_level":"low",'
            '"requires_rag":false,"requires_command":false,"should_execute":true,'
            '"candidate_commands":[],"candidate_skills":[],"candidate_mcp_tools":["browser_search"],'
            '"capability_requirements":[{"kind":"mcp_tool","freshness":"realtime",'
            '"scope":"public_external","execution_mode":"retrieve","required":true,'
            '"reason":"需要联网查询公开信息"}],'
            '"steps":["调用 browser_search 检索实时公开信息"],"confirmation_question":null,'
            '"reason":"当前问题需要联网搜索公开热点。"}'
        ),
        (
            "我会先联网查询最近的公开热点信息，然后整理结果告诉你。"
            "\n<hr/>\n"
            '{"tasks":[{"task_type":"mcp_tool","command":"browser_search","params":[{"type":"text","value":"最近网上有什么热点","separate":false}]}],'
            '"need_confirm":false,"is_violation":false}'
        ),
    ]
    calls = patch_pipeline_llm(monkeypatch, responses)

    pipeline = MessageProcessingPipeline(
        build_helpers_with_semantic_commands(),
        Messages(),
        trace_id="semantic-mcp-hot-topics",
    )
    pipeline.policy.mcp_tools = MCPToolCatalog(
        tools=[
            MCPTool(
                name="browser_search",
                description="联网搜索公开热点",
                domain_tags=["web_search", "news"],
                freshness="realtime",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                server_url="http://127.0.0.1:8000/mcp",
            )
        ],
        tool_index={
            "browser_search": MCPTool(
                name="browser_search",
                description="联网搜索公开热点",
                domain_tags=["web_search", "news"],
                freshness="realtime",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                server_url="http://127.0.0.1:8000/mcp",
            )
        },
    )
    pipeline.mcp_tools = pipeline.policy.mcp_tools

    async def fake_ensure_mcp_tools() -> None:
        return None

    monkeypatch.setattr(pipeline, "ensure_mcp_tools", fake_ensure_mcp_tools)

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="最近网上有什么热点")]))

    assert calls
    assert result.route is not None
    assert result.route.intent == "complex_task"
    assert result.plan is not None
    assert result.plan.candidate_mcp_tools == ["browser_search"]
    assert result.auto_tasks is not None
    assert result.auto_tasks.tasks[0].task_type == "mcp_tool"
    assert result.auto_tasks.tasks[0].command == "browser_search"
    assert result.auto_tasks.tasks[0].params[0].value == '{"query": "最近网上有什么热点"}'


@pytest.mark.asyncio
async def test_realtime_hot_topic_query_synthesizes_mcp_task_when_task_stage_returns_empty(loaded_plugins, monkeypatch):
    from src.core.mcp.schema import MCPTool
    from src.core.mcp.catalog import MCPToolCatalog
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.schema import ChatMessage
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    responses = [
        (
            '{"intent":"complex_task","reply":null,"requires_rag":false,"requires_command":false,'
            '"need_confirm":false,"reason":"需要调用实时公共外部检索能力","knowledge_sources":[],'
            '"capability_requirements":[{"kind":"mcp_tool","freshness":"realtime",'
            '"scope":"public_external","execution_mode":"retrieve","required":true,'
            '"reason":"需要联网查询公开信息"}],"unavailable_reason":null}'
        ),
        extract_response("最近网上有什么热点"),
        (
            '{"goal":"查询最近网上热点","facts":[],"missing_info":[],"risk_level":"low",'
            '"requires_rag":false,"requires_command":false,"should_execute":true,'
            '"candidate_commands":[],"candidate_skills":[],"candidate_mcp_tools":["browser_search"],'
            '"capability_requirements":[{"kind":"mcp_tool","freshness":"realtime",'
            '"scope":"public_external","execution_mode":"retrieve","required":true,'
            '"reason":"需要联网查询公开信息"}],'
            '"steps":["调用 browser_search 检索实时公开信息"],"confirmation_question":null,'
            '"reason":"当前问题需要联网搜索公开热点。"}'
        ),
        "我现在去查一下最近的公开热点，请稍候。",
    ]
    patch_pipeline_llm(monkeypatch, responses)

    pipeline = MessageProcessingPipeline(
        build_helpers_with_semantic_commands(),
        Messages(),
        trace_id="semantic-mcp-hot-topics-fallback",
    )
    pipeline.policy.mcp_tools = MCPToolCatalog(
        tools=[
            MCPTool(
                name="browser_search",
                description="联网搜索公开热点",
                domain_tags=["web_search", "news"],
                freshness="realtime",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                server_url="http://127.0.0.1:8000/mcp",
            )
        ],
        tool_index={
            "browser_search": MCPTool(
                name="browser_search",
                description="联网搜索公开热点",
                domain_tags=["web_search", "news"],
                freshness="realtime",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                server_url="http://127.0.0.1:8000/mcp",
            )
        },
    )
    pipeline.mcp_tools = pipeline.policy.mcp_tools

    async def fake_ensure_mcp_tools() -> None:
        return None

    monkeypatch.setattr(pipeline, "ensure_mcp_tools", fake_ensure_mcp_tools)

    result = await pipeline.process(ChatMessage(message=[Content(type="text", value="最近网上有什么热点")]))

    assert result.auto_tasks is not None
    assert result.auto_tasks.tasks
    assert result.auto_tasks.tasks[0].task_type == "mcp_tool"
    assert result.auto_tasks.tasks[0].command == "browser_search"
    assert result.auto_tasks.tasks[0].params[0].value == '{"query": "最近网上有什么热点"}'
