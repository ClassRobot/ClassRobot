import pytest


def test_loop_budget_stops_after_verify_attempt_limit(loaded_plugins):
    from src.core.agent.runtime.loop import LoopBudget, AgentLoopConfig, AgentLoopDecision

    budget = LoopBudget(
        AgentLoopConfig(
            max_steps=8,
            max_verify_attempts=3,
            max_repeat_actions=3,
            max_runtime_seconds=120,
        )
    )
    decision = AgentLoopDecision(
        action_type="verify",
        capability_name="查询任务",
        verify_target="任务:收作业",
    )

    for _ in range(3):
        assert budget.check(decision) is None
        budget.consume(decision)

    blocked_reason = budget.check(decision)

    assert blocked_reason is not None
    assert "最多验证 3 次" in blocked_reason
    assert budget.stop_reason == "max_verify_attempts"


def test_observation_interpreter_extracts_generic_facts(loaded_plugins):
    from src.core.agent.runtime.loop import ObservationInterpreter
    from src.core.agent.runtime.schema import Param, CommandObservation

    interpreter = ObservationInterpreter()

    missing_fact = interpreter.interpret(
        CommandObservation(
            command="查询任务",
            success=True,
            message="没有找到符合条件的记录。",
            params=[Param(type="text", value="收作业")],
        )
    )
    changed_fact = interpreter.interpret(
        CommandObservation(
            command="创建任务",
            success=True,
            message="任务已经创建。",
            params=[Param(type="text", value="收作业")],
        )
    )
    verified_fact = interpreter.interpret(
        CommandObservation(
            command="查询任务",
            success=True,
            outputs=["任务：收作业，状态：进行中"],
            params=[Param(type="text", value="收作业")],
        )
    )

    assert missing_fact.exists is False
    assert "create_or_update" in missing_fact.suggested_next_actions
    assert changed_fact.changed is True
    assert "verify" in changed_fact.suggested_next_actions
    assert verified_fact.verified is True
    assert verified_fact.exists is True


def test_loop_stop_reply_hides_mcp_internal_tool_names(loaded_plugins):
    from src.core.agent.runtime.loop import CognitiveAgentLoop
    from src.core.agent.runtime.schema import CommandObservation

    reply = CognitiveAgentLoop.build_stop_reply(
        "执行过程中有一步没有完成。",
        attempted_observations=[],
        all_observations=[
            CommandObservation(
                command="browser_open",
                source_type="mcp_tool",
                dispatch_type="mcp_tool",
                success=False,
                message="外部工具调用失败。",
            )
        ],
    )

    assert "外部查询工具" in reply
    assert "browser_open" not in reply


@pytest.mark.asyncio
async def test_cognitive_loop_stops_after_max_steps(loaded_plugins):
    from src.core.agent.runtime.loop import AgentLoopConfig, CognitiveAgentLoop
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep, CommandObservation

    calls: list[str] = []

    async def dispatch(task):
        calls.append(task.command)
        return [
            CommandObservation(
                command=task.command,
                success=True,
                message="命令已完成。",
            )
        ]

    workflow = TaskWorkflow(
        trace_id="autogpt-loop-max-steps",
        kind="command_sequence",
        steps=[
            WorkflowStep(step_id="step-1", title="查询班级", command="查询班级"),
            WorkflowStep(step_id="step-2", title="查询课表", command="查询课表"),
        ],
    )

    execution = await CognitiveAgentLoop(
        dispatch,
        config=AgentLoopConfig(
            max_steps=1,
            max_verify_attempts=3,
            max_repeat_actions=3,
            max_runtime_seconds=120,
        ),
    ).execute(workflow)

    assert calls == ["查询班级"]
    assert execution.workflow.status == "failed"
    assert "最多执行 1 步" in (execution.user_message or "")
    assert [step.status for step in execution.workflow.steps] == ["completed", "pending"]


@pytest.mark.asyncio
async def test_cognitive_loop_stops_repeated_actions(loaded_plugins):
    from src.core.agent.runtime.loop import AgentLoopConfig, CognitiveAgentLoop
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep, CommandObservation

    calls: list[str] = []

    async def dispatch(task):
        calls.append(task.command)
        return [
            CommandObservation(
                command=task.command,
                success=True,
                message="命令已完成。",
            )
        ]

    workflow = TaskWorkflow(
        trace_id="autogpt-loop-repeat",
        kind="command_sequence",
        steps=[
            WorkflowStep(step_id="step-1", title="查询任务", command="查询任务"),
            WorkflowStep(step_id="step-2", title="查询任务", command="查询任务"),
            WorkflowStep(step_id="step-3", title="查询任务", command="查询任务"),
        ],
    )

    execution = await CognitiveAgentLoop(
        dispatch,
        config=AgentLoopConfig(
            max_steps=8,
            max_verify_attempts=3,
            max_repeat_actions=2,
            max_runtime_seconds=120,
        ),
    ).execute(workflow)

    assert calls == ["查询任务", "查询任务"]
    assert execution.workflow.status == "failed"
    assert "最多重复 2 次" in (execution.user_message or "")
    assert [step.status for step in execution.workflow.steps] == ["completed", "completed", "pending"]


@pytest.mark.asyncio
async def test_cognitive_loop_can_add_followup_from_observation_without_domain_branch(loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.agent.runtime.command_tools import CommandToolCatalog
    from src.core.agent.runtime.loop import AgentLoopConfig, AgentLoopDecision, CognitiveAgentLoop
    from src.core.agent.runtime.schema import Param, TaskWorkflow, WorkflowStep, CommandObservation

    from tests.autogpt.command_tool_helpers import ensure_service_helper

    helpers = Helpers()
    helpers.append(ensure_service_helper("测试查询目标", "查询目标是否存在"))
    helpers.append(ensure_service_helper("测试创建目标", "创建一个目标"))
    command_tools = CommandToolCatalog.from_helpers(helpers)
    calls: list[str] = []

    async def dispatch(task):
        calls.append(task.command)
        if task.command == "测试查询目标":
            return [
                CommandObservation(
                    command=task.command,
                    params=task.params,
                    success=True,
                    message="没有找到符合条件的记录。",
                )
            ]
        return [
            CommandObservation(
                command=task.command,
                params=task.params,
                success=True,
                message="任务已经创建。",
            )
        ]

    async def decide(workflow, pending_steps, observations, facts, budget):
        if pending_steps:
            return AgentLoopDecision.from_step(pending_steps[0])
        if facts and facts[-1].exists is False:
            return AgentLoopDecision(
                action_type="command",
                capability_name="测试创建目标",
                params=[Param(type="text", value="收作业")],
                reason="观察显示目标不存在，能力目录中存在创建类能力。",
            )
        return AgentLoopDecision(action_type="finish", reason="已有观察足够回复用户。")

    workflow = TaskWorkflow(
        trace_id="autogpt-loop-followup",
        kind="command",
        goal="帮我创建收作业任务",
        steps=[
            WorkflowStep(
                step_id="step-1",
                title="先查询任务是否存在",
                command="测试查询目标",
                params=[Param(type="text", value="收作业")],
            )
        ],
    )

    execution = await CognitiveAgentLoop(
        dispatch,
        command_tools=command_tools,
        config=AgentLoopConfig(
            max_steps=8,
            max_verify_attempts=3,
            max_repeat_actions=2,
            max_runtime_seconds=120,
        ),
        decision_provider=decide,
    ).execute(workflow)

    assert calls == ["测试查询目标", "测试创建目标"]
    assert execution.workflow.status == "completed"
    assert [observation.command for observation in execution.observations] == ["测试查询目标", "测试创建目标"]
    assert execution.workflow.steps[-1].command == "测试创建目标"


@pytest.mark.asyncio
async def test_cognitive_loop_supports_confirm_decision_without_command(loaded_plugins):
    from src.core.agent.runtime.schema import TaskWorkflow, WorkflowStep
    from src.core.agent.runtime.loop import AgentLoopConfig, AgentLoopDecision, CognitiveAgentLoop

    async def dispatch(task):
        raise AssertionError("confirm decision should not dispatch command")

    async def decide(workflow, pending_steps, observations, facts, budget):
        return AgentLoopDecision(
            action_type="confirm",
            reason="这个操作还缺少班级范围，请先告诉我要发布到哪个班级。",
        )

    workflow = TaskWorkflow(
        trace_id="autogpt-loop-confirm",
        kind="command",
        goal="发布一个任务",
        steps=[WorkflowStep(step_id="step-1", title="准备发布任务", command="测试发布目标")],
    )

    execution = await CognitiveAgentLoop(
        dispatch,
        config=AgentLoopConfig(
            max_steps=8,
            max_verify_attempts=3,
            max_repeat_actions=2,
            max_runtime_seconds=120,
        ),
        decision_provider=decide,
    ).execute(workflow)

    assert execution.workflow.status == "needs_confirm"
    assert execution.workflow.need_confirm is True
    assert execution.workflow.approval.status == "pending"
    assert "班级范围" in (execution.user_message or "")


@pytest.mark.asyncio
async def test_cognitive_loop_runs_mcp_tool_with_budget(loaded_plugins):
    from src.core.mcp.catalog import MCPToolCatalog
    from src.core.mcp.schema import MCPTool, MCPCallResult
    from src.core.agent.runtime.loop import AgentLoopConfig, CognitiveAgentLoop
    from src.core.agent.runtime.schema import Param, TaskWorkflow, WorkflowStep

    class FakeMCPClient:
        async def call_tool(self, tool_name, arguments):
            assert tool_name == "search_docs"
            assert arguments == {"query": "作业"}
            return MCPCallResult(
                tool_name=tool_name,
                success=True,
                display_text="检索完成。",
                context_summary="外部文档中有作业要求。",
            )

    async def dispatch(task):
        raise AssertionError("mcp_tool action should not dispatch command")

    catalog = MCPToolCatalog()
    catalog.append(MCPTool(name="search_docs", description="检索外部文档"))
    workflow = TaskWorkflow(
        trace_id="autogpt-loop-mcp",
        kind="command",
        steps=[
            WorkflowStep(
                step_id="step-1",
                step_type="mcp_tool",
                title="调用 MCP 工具",
                command="search_docs",
                params=[Param(type="text", value='{"query":"作业"}')],
            )
        ],
    )

    execution = await CognitiveAgentLoop(
        dispatch,
        mcp_tools=catalog,
        mcp_client=FakeMCPClient(),
        config=AgentLoopConfig(
            max_steps=1,
            max_verify_attempts=3,
            max_repeat_actions=2,
            max_runtime_seconds=120,
        ),
    ).execute(workflow)

    assert execution.workflow.status == "completed"
    assert execution.observations[0].dispatch_type == "mcp_tool"
    assert execution.observations[0].context_outputs == ["外部文档中有作业要求。"]


@pytest.mark.asyncio
async def test_cognitive_loop_injects_mcp_session_from_previous_observation(loaded_plugins):
    from src.core.mcp.catalog import MCPToolCatalog
    from src.core.mcp.schema import MCPTool, MCPCallResult
    from src.core.agent.runtime.loop import AgentLoopConfig, CognitiveAgentLoop
    from src.core.agent.runtime.schema import Param, TaskWorkflow, WorkflowStep

    calls: list[tuple[str, dict]] = []

    class FakeMCPClient:
        async def call_tool(self, tool_name, arguments):
            calls.append((tool_name, arguments))
            if tool_name == "browser_create_session":
                return MCPCallResult(
                    tool_name=tool_name,
                    success=True,
                    display_text='{"session_id":"session-123"}',
                    context_summary="浏览会话已创建。",
                    raw_result={"content": [{"text": '{"session_id":"session-123"}'}]},
                )
            return MCPCallResult(
                tool_name=tool_name,
                success=True,
                display_text="网页已打开。",
                context_summary="GitHub 项目页已打开。",
            )

    async def dispatch(task):
        raise AssertionError("mcp_tool action should not dispatch command")

    catalog = MCPToolCatalog()
    catalog.append(MCPTool(name="browser_create_session", description="创建浏览器会话"))
    catalog.append(
        MCPTool(
            name="browser_open",
            description="打开网页",
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["session_id", "url"],
            },
        )
    )
    workflow = TaskWorkflow(
        trace_id="autogpt-loop-mcp-session",
        kind="command_sequence",
        goal="打开 GitHub 项目页",
        steps=[
            WorkflowStep(
                step_id="step-1",
                step_type="mcp_tool",
                title="创建浏览器会话",
                command="browser_create_session",
            ),
            WorkflowStep(
                step_id="step-2",
                step_type="mcp_tool",
                title="打开项目页",
                command="browser_open",
                params=[Param(type="text", value="https://github.com/ClassRobot/ClassRobot")],
            ),
        ],
    )

    execution = await CognitiveAgentLoop(
        dispatch,
        mcp_tools=catalog,
        mcp_client=FakeMCPClient(),
        config=AgentLoopConfig(
            max_steps=3,
            max_verify_attempts=3,
            max_repeat_actions=2,
            max_runtime_seconds=120,
        ),
    ).execute(workflow)

    assert execution.workflow.status == "completed"
    assert calls[0] == ("browser_create_session", {})
    assert calls[1] == (
        "browser_open",
        {
            "session_id": "session-123",
            "url": "https://github.com/ClassRobot/ClassRobot",
        },
    )


@pytest.mark.asyncio
async def test_cognitive_loop_reports_progress_before_mcp_call(loaded_plugins):
    from src.core.mcp.catalog import MCPToolCatalog
    from src.core.mcp.schema import MCPTool, MCPCallResult
    from src.core.agent.runtime.loop import AgentLoopConfig, CognitiveAgentLoop
    from src.core.agent.runtime.schema import Param, TaskWorkflow, WorkflowStep

    class FakeMCPClient:
        async def call_tool(self, tool_name, arguments):
            return MCPCallResult(
                tool_name=tool_name,
                success=True,
                display_text="检索完成。",
                context_summary="外部文档中有作业要求。",
            )

    async def dispatch(task):
        raise AssertionError("mcp_tool action should not dispatch command")

    reports: list[str] = []

    async def report(message: str) -> None:
        reports.append(message)

    catalog = MCPToolCatalog()
    catalog.append(MCPTool(name="search_docs", description="检索外部文档"))
    workflow = TaskWorkflow(
        trace_id="autogpt-loop-mcp-progress",
        kind="command",
        steps=[
            WorkflowStep(
                step_id="step-1",
                step_type="mcp_tool",
                title="调用 MCP 工具",
                command="search_docs",
                params=[Param(type="text", value='{"query":"作业"}')],
            )
        ],
    )

    execution = await CognitiveAgentLoop(
        dispatch,
        mcp_tools=catalog,
        mcp_client=FakeMCPClient(),
        progress_reporter=report,
        config=AgentLoopConfig(
            max_steps=1,
            max_verify_attempts=3,
            max_repeat_actions=2,
            max_runtime_seconds=120,
        ),
    ).execute(workflow)

    assert execution.workflow.status == "completed"
    assert reports == ["我正在调用联网检索工具查询公开信息，请稍等。"]


@pytest.mark.asyncio
async def test_cognitive_loop_rewrites_low_relevance_mcp_query_once(loaded_plugins):
    from src.core.mcp.catalog import MCPToolCatalog
    from src.core.mcp.schema import MCPTool, MCPCallResult
    from src.core.agent.runtime.loop import AgentLoopConfig, CognitiveAgentLoop
    from src.core.agent.runtime.schema import Param, TaskWorkflow, WorkflowStep

    calls: list[dict] = []

    class FakeMCPClient:
        async def call_tool(self, tool_name, arguments):
            calls.append(arguments)
            if len(calls) == 1:
                return MCPCallResult(
                    tool_name=tool_name,
                    success=True,
                    display_text="1. 20 best parks in London - visitlondon.com",
                    context_summary="London parks travel pages.",
                )
            return MCPCallResult(
                tool_name=tool_name,
                success=True,
                display_text="中文互联网热点：科技产品发布、校园新闻、文娱热搜。",
                context_summary="检索到中文热点摘要。",
            )

    async def dispatch(task):
        raise AssertionError("mcp_tool action should not dispatch command")

    catalog = MCPToolCatalog()
    catalog.append(MCPTool(name="browser_search", description="联网搜索公开热点"))
    workflow = TaskWorkflow(
        trace_id="autogpt-loop-mcp-low-relevance",
        kind="command",
        goal="最近网上有什么热点",
        steps=[
            WorkflowStep(
                step_id="step-1",
                step_type="mcp_tool",
                title="调用 MCP 工具",
                command="browser_search",
                params=[Param(type="text", value='{"query":"最近网上有什么热点"}')],
            )
        ],
    )

    execution = await CognitiveAgentLoop(
        dispatch,
        mcp_tools=catalog,
        mcp_client=FakeMCPClient(),
        config=AgentLoopConfig(
            max_steps=3,
            max_verify_attempts=3,
            max_repeat_actions=2,
            max_runtime_seconds=120,
        ),
    ).execute(workflow)

    assert len(calls) == 2
    assert calls[0] == {"query": "最近网上有什么热点"}
    assert "中文互联网" in calls[1]["query"]
    assert execution.observations[0].relevance == "low"
    assert execution.observations[-1].relevance in {"medium", "high"}
