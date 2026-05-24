from src.core.mcp.schema import MCPCallResult


def test_params_to_arguments_parses_json_object(loaded_plugins):
    from src.core.mcp.observation import params_to_arguments
    from src.core.agent.runtime.schema import Param

    params = [Param(type="text", value='{"query":"作业"}')]

    assert params_to_arguments(params) == {"query": "作业"}


def test_mcp_result_to_observation_uses_mcp_dispatch_type(loaded_plugins):
    from src.core.mcp.observation import mcp_result_to_observation
    from src.core.agent.runtime.schema import Param

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
