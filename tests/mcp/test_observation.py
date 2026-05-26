from src.core.mcp.schema import MCPCallResult


def test_params_to_arguments_parses_json_object(loaded_plugins):
    from src.core.agent.runtime.schema import Param
    from src.core.mcp.observation import params_to_arguments

    params = [Param(type="text", value='{"query":"作业"}')]

    assert params_to_arguments(params) == {"query": "作业"}


def test_params_to_arguments_maps_positional_url_and_prior_session(loaded_plugins):
    from src.core.mcp.observation import params_to_arguments
    from src.core.agent.runtime.schema import Param, CommandObservation

    input_schema = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "url": {"type": "string"},
        },
        "required": ["session_id", "url"],
    }
    params = [Param(type="text", value="https://github.com/ClassRobot/ClassRobot")]
    prior_observations = [
        CommandObservation(
            command="browser_create_session",
            source_type="mcp_tool",
            dispatch_type="mcp_tool",
            raw_result={"content": [{"text": '{"session_id":"session-123"}'}]},
            success=True,
        )
    ]

    assert params_to_arguments(params, input_schema, prior_observations) == {
        "session_id": "session-123",
        "url": "https://github.com/ClassRobot/ClassRobot",
    }


def test_mcp_result_to_observation_uses_mcp_dispatch_type(loaded_plugins):
    from src.core.agent.runtime.schema import Param
    from src.core.mcp.observation import mcp_result_to_observation

    params = [Param(type="text", value='{"query":"作业"}')]
    result = MCPCallResult(
        tool_name="search_docs",
        success=True,
        display_text="检索到 1 条资料。",
        context_summary="外部文档显示有作业要求。",
    )

    observation = mcp_result_to_observation("trace-mcp", params, result)

    assert observation.dispatch_type == "mcp_tool"
    assert observation.command == "search_docs"
    assert observation.success is True
    assert observation.outputs_sent_to_user is False
    assert observation.context_outputs == ["外部文档显示有作业要求。"]
    assert observation.source_type == "mcp_tool"
    assert observation.tool_name == "search_docs"
    assert observation.query == "作业"
    assert observation.display_summary == "检索到 1 条资料。"


def test_mcp_observation_marks_obviously_irrelevant_search_result(loaded_plugins):
    from src.core.agent.runtime.schema import Param
    from src.core.mcp.observation import mcp_result_to_observation
    from src.core.agent.runtime.observation_quality import ObservationQualityGate

    params = [Param(type="text", value='{"query":"最近网上有什么热点"}')]
    result = MCPCallResult(
        tool_name="browser_search",
        success=True,
        display_text="1. 20 best parks in London - visitlondon.com\n2. Hyde Park guide",
        context_summary="London parks and visitlondon travel pages.",
    )

    observation = mcp_result_to_observation("trace-mcp-low", params, result)
    observation = ObservationQualityGate().evaluate(observation, user_goal="最近网上有什么热点")

    assert observation.relevance == "low"
    assert observation.answer_quality == "insufficient"
    assert "不能作为可靠答案" in observation.display_summary
    assert "retry_search" in observation.next_actions
