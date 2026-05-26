from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


def llm_response(content: str) -> SimpleNamespace:
    """构造 OpenAI SDK 风格的最小响应。"""

    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.mark.asyncio
async def test_hot_topic_mcp_flow_retries_summarizes_and_supports_followup(
    loaded_plugins,
    monkeypatch,
):
    from src.platform.helper import Helpers
    from src.core.mcp.client import MCPClient
    from src.core.agent.runtime.util import ChatSession
    from src.core.mcp.schema import MCPTool, MCPCallResult
    import src.core.agent.builtin.planning as planning_module
    from src.core.agent.runtime import pipeline as pipeline_module
    import src.core.agent.builtin.conversation as conversation_module

    llm_calls: list[str] = []
    captured_reply_prompt = ""

    responses = [
        (
            '{"intent":"complex_task","reply":null,"requires_rag":false,"requires_command":false,'
            '"need_confirm":false,"reason":"需要调用实时公共外部检索能力","knowledge_sources":[],'
            '"capability_requirements":[{"kind":"mcp_tool","freshness":"realtime",'
            '"scope":"public_external","execution_mode":"retrieve","required":true,'
            '"reason":"需要联网查询公开热点"}],"unavailable_reason":null}'
        ),
        json.dumps({"role": "user", "content": [{"type": "text", "value": "最近网上有什么热点"}]}, ensure_ascii=False),
        (
            '{"goal":"查询最近网上热点","facts":[],"missing_info":[],"risk_level":"low",'
            '"requires_rag":false,"requires_command":false,"should_execute":true,'
            '"candidate_commands":[],"candidate_skills":[],"candidate_mcp_tools":["browser_search"],'
            '"capability_requirements":[{"kind":"mcp_tool","freshness":"realtime",'
            '"scope":"public_external","execution_mode":"retrieve","required":true,'
            '"reason":"需要联网查询公开热点"}],'
            '"steps":["调用 browser_search 检索实时公开信息"],"confirmation_question":null,'
            '"reason":"当前问题需要联网搜索公开热点。"}'
        ),
        (
            "我会先联网查询最近公开热点，再整理成中文结论。"
            "\n<hr/>\n"
            '{"tasks":[{"task_type":"mcp_tool","command":"browser_search",'
            '"params":[{"type":"text","value":"最近网上有什么热点","separate":false}]}],'
            '"need_confirm":false,"is_violation":false}'
        ),
        "我查到了最近的公开热点，可以先概括成三类：科技产品动态、校园与教育话题、文娱热搜。第五条没有可靠来源，所以我不会编造。",
        (
            '{"intent":"chat","reply":null,"requires_rag":false,"requires_command":false,'
            '"need_confirm":false,"reason":"追问上一轮最终回复中的条目",'
            '"knowledge_sources":[],"capability_requirements":[{"kind":"direct_chat",'
            '"freshness":"static","scope":"public_external","execution_mode":"answer",'
            '"required":true,"reason":"基于上一轮最终回复回答"}],"unavailable_reason":null}'
        ),
        "上一轮我只可靠总结了三类热点，没有确认到第 5 条，所以我不能编造成第五条。",
    ]

    async def fake_client_create(messages, **kwargs):
        nonlocal captured_reply_prompt
        task_type = str(kwargs.get("task_type") or "")
        llm_calls.append(task_type)
        if "reply" in task_type and len(llm_calls) >= 5:
            captured_reply_prompt = "\n\n".join(message.single_modal() for message in messages.messages)
        if not responses:
            raise AssertionError("fake LLM responses exhausted")
        return llm_response(responses.pop(0))

    async def fake_list_tools(self):
        return [
            MCPTool(
                name="browser_search",
                description="联网搜索公开信息和新闻热点",
                domain_tags=["web_search", "news"],
                freshness="realtime",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                server_url="http://127.0.0.1:8000/mcp",
            )
        ]

    mcp_calls: list[tuple[str, dict]] = []

    async def fake_call_tool(self, tool_name, arguments):
        mcp_calls.append((tool_name, arguments))
        if len(mcp_calls) == 1:
            return MCPCallResult(
                tool_name=tool_name,
                success=True,
                display_text="1. 20 best parks in London - visitlondon.com\n2. Hyde Park guide",
                context_summary="London parks and visitlondon travel pages.",
            )
        return MCPCallResult(
            tool_name=tool_name,
            success=True,
            display_text=(
                "1. AI phone launch: global tech updates\n"
                "2. Education policy discussion\n"
                "3. Entertainment trending topic"
            ),
            context_summary="中文互联网热点摘要：科技产品动态、教育话题、文娱热搜。",
        )

    monkeypatch.setattr(pipeline_module, "client_create", fake_client_create)
    monkeypatch.setattr(planning_module, "client_create", fake_client_create)
    monkeypatch.setattr(conversation_module, "client_create", fake_client_create)
    monkeypatch.setattr(MCPClient, "list_tools", fake_list_tools)
    monkeypatch.setattr(MCPClient, "call_tool", fake_call_tool)

    session = ChatSession(user_id=1, helpers=Helpers())

    turn_result = await session.send_message("最近网上有什么热点")
    assert turn_result.auto_tasks is not None
    assert turn_result.auto_tasks.tasks[0].task_type == "mcp_tool"
    assert turn_result.workflow is not None
    assert turn_result.workflow.steps

    execution = await session.execute_task_workflow(turn_result.workflow, dispatcher=lambda task: [])

    assert [call[0] for call in mcp_calls] == ["browser_search", "browser_search"]
    assert mcp_calls[0][1] == {"query": "最近网上有什么热点"}
    assert "中文互联网" in mcp_calls[1][1]["query"]
    assert execution.observations[0].relevance == "low"
    assert execution.observations[-1].answer_quality in {"complete", "partial"}
    assert "中文互联网热点摘要" in (execution.user_message or "")
    assert "London parks" not in (execution.final_reply or "")
    assert "公开热点" in (execution.final_reply or "")
    assert '"relevance": "low"' in captured_reply_prompt
    assert any("# 系统最终回复记录" in message.single_modal() for message in session.messages.messages)

    followup_result = await session.send_message("第五条是什么")

    assert followup_result.auto_tasks is not None
    assert followup_result.auto_tasks.tasks == []
    assert "没有确认到第 5 条" in (followup_result.auto_tasks.reply or "")
    assert len(mcp_calls) == 2
