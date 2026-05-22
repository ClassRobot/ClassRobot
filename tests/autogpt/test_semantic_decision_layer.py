import pytest

from tests.autogpt.semantic_helpers import (
    task_response,
    plan_response,
    route_response,
    extract_response,
    patch_pipeline_llm,
    build_helpers_with_semantic_commands,
)


@pytest.mark.asyncio
async def test_self_identity_query_uses_ai_route_and_plans_self_info(loaded_plugins, monkeypatch):
    from src.core.llm.message import Content, Messages
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.schema import ChatMessage

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
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.schema import ChatMessage

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
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.llm.message import Content, Context, LLMRole, Messages

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
    from src.core.agent.runtime.node_registry import DEFAULT_RUNTIME_NODE_ORDER, RUNTIME_NODE_REGISTRY
    from src.core.agent.runtime.orchestration_config import default_graph_config

    graph = default_graph_config()

    assert "local_context" not in RUNTIME_NODE_REGISTRY
    assert "local_chat_statistics" not in RUNTIME_NODE_REGISTRY
    assert "local_context" not in DEFAULT_RUNTIME_NODE_ORDER
    assert "local_chat_statistics" not in DEFAULT_RUNTIME_NODE_ORDER
    assert "local_context" not in graph.node_order
    assert "local_chat_statistics" not in graph.node_order
    assert ("append_user_message", "route") in {(edge.source, edge.target) for edge in graph.edges}
