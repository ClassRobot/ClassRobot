import pytest


def test_build_turn_result_promotes_tasks_to_explicit_workflow(loaded_plugins):
    from src.plugins.autogpt.workflow import build_turn_result
    from src.plugins.autogpt.command_tools import CommandToolCatalog
    from src.plugins.autogpt.schema import Param, AutoTask, AgentPlan, IntentRoute, AutoTaskList

    from utils.helper import Helper, Helpers

    helpers = Helpers()
    helpers.append(Helper(command="添加班级", description="添加一个班级"))
    helpers.append(Helper(command="创建通知", description="创建班级通知"))

    result = build_turn_result(
        trace_id="autogpt-workflow",
        route=IntentRoute(intent="complex_task", requires_command=True, reason="用户要完成多步班级事务"),
        plan=AgentPlan(
            goal="创建班级并发送通知",
            requires_command=True,
            should_execute=True,
            candidate_commands=["添加班级", "创建通知"],
            steps=["先创建班级", "再发送通知"],
            reason="当前目标需要两个项目命令顺序完成。",
        ),
        auto_tasks=AutoTaskList(
            reply="我会先帮你创建班级，再帮你发送通知。",
            tasks=[
                AutoTask(command="添加班级", params=[Param(type="text", value="一班")]),
                AutoTask(command="创建通知", params=[Param(type="text", value="明天带作业")]),
            ],
        ),
        command_tools=CommandToolCatalog.from_helpers(helpers),
    )

    assert result.workflow is not None
    assert result.workflow.kind == "command_sequence"
    assert result.workflow.status == "planned"
    assert result.workflow.goal == "创建班级并发送通知"
    assert [step.command for step in result.workflow.steps] == ["添加班级", "创建通知"]
    assert result.workflow.steps[0].risk_level == "medium"
    assert result.workflow.steps[1].risk_level == "high"
    assert result.workflow.approval.type == "none"
    assert result.workflow.approval.status == "not_required"
    assert [event.event_type for event in result.workflow.events] == ["workflow_created"]


def test_build_turn_result_marks_high_risk_workflow_for_approval(loaded_plugins):
    from src.plugins.autogpt.workflow import build_turn_result
    from src.plugins.autogpt.command_tools import CommandToolCatalog
    from src.plugins.autogpt.schema import Param, AutoTask, AgentPlan, IntentRoute, AutoTaskList

    from utils.helper import Helper, Helpers

    helpers = Helpers()
    helpers.append(Helper(command="创建通知", description="创建班级通知"))

    result = build_turn_result(
        trace_id="autogpt-approval",
        route=IntentRoute(intent="command", requires_command=True, need_confirm=True, reason="高风险命令需要确认"),
        plan=AgentPlan(
            goal="向班级发送通知",
            risk_level="high",
            requires_command=True,
            should_execute=False,
            confirmation_question="要现在发送这条通知吗？",
            reason="群发类操作需要用户确认。",
        ),
        auto_tasks=AutoTaskList(
            reply="要现在发送这条通知吗？",
            need_confirm=True,
            tasks=[AutoTask(command="创建通知", params=[Param(type="text", value="明天开班会")])],
        ),
        command_tools=CommandToolCatalog.from_helpers(helpers),
    )

    assert result.workflow is not None
    assert result.workflow.need_confirm is True
    assert result.workflow.approval.required is True
    assert result.workflow.approval.type == "high_risk"
    assert result.workflow.approval.status == "pending"
    assert result.workflow.approval.prompt == "要现在发送这条通知吗？"
    assert result.workflow.steps[0].approval.type == "high_risk"
    assert result.workflow.steps[0].approval.status == "pending"
    assert [event.event_type for event in result.workflow.events] == ["workflow_created", "approval_requested"]


def test_build_turn_result_marks_missing_info_approval(loaded_plugins):
    from src.plugins.autogpt.workflow import build_turn_result
    from src.plugins.autogpt.command_tools import CommandToolCatalog
    from src.plugins.autogpt.schema import AgentPlan, IntentRoute, AutoTaskList

    from utils.helper import Helpers

    result = build_turn_result(
        trace_id="autogpt-missing-info",
        route=IntentRoute(intent="command", requires_command=True, need_confirm=True, reason="参数不完整"),
        plan=AgentPlan(
            goal="创建班级任务",
            requires_command=True,
            should_execute=False,
            missing_info=["班级名称", "任务内容"],
            confirmation_question="还缺少班级名称和任务内容。",
            reason="需要先补充参数。",
        ),
        auto_tasks=AutoTaskList(reply="还缺少班级名称和任务内容。", need_confirm=True, tasks=[]),
        command_tools=CommandToolCatalog.from_helpers(Helpers()),
    )

    assert result.workflow is not None
    assert result.workflow.need_confirm is True
    assert result.workflow.approval.type == "missing_info"
    assert result.workflow.approval.status == "pending"
    assert result.workflow.approval.missing_info == ["班级名称", "任务内容"]
    assert [event.event_type for event in result.workflow.events] == ["workflow_created", "approval_requested"]


@pytest.mark.asyncio
async def test_workflow_executor_runs_steps_in_order(loaded_plugins):
    from src.plugins.autogpt.workflow import WorkflowExecutor
    from src.plugins.autogpt.schema import Param, WorkflowStep, AgentWorkflow, CommandObservation

    calls: list[str] = []

    async def dispatch(task):
        calls.append(task.command)
        return [
            CommandObservation(
                trace_id="autogpt-exec",
                command=task.command,
                params=task.params,
                success=True,
                message="命令已投递给 NoneBot 事件系统。",
            )
        ]

    workflow = AgentWorkflow(
        trace_id="autogpt-exec",
        kind="command_sequence",
        goal="批量处理班级事务",
        steps=[
            WorkflowStep(
                step_id="step-1",
                title="执行命令：添加班级",
                command="添加班级",
                params=[Param(type="text", value="一班")],
            ),
            WorkflowStep(
                step_id="step-2",
                title="执行命令：创建通知",
                command="创建通知",
                params=[Param(type="text", value="明天开班会")],
            ),
        ],
    )

    execution = await WorkflowExecutor(dispatch).execute(workflow)

    assert calls == ["添加班级", "创建通知"]
    assert execution.workflow.status == "completed"
    assert [step.status for step in execution.workflow.steps] == ["completed", "completed"]
    assert execution.user_message is None
    assert [event.event_type for event in execution.workflow.events] == [
        "workflow_started",
        "step_started",
        "step_completed",
        "step_started",
        "step_completed",
        "workflow_completed",
    ]


@pytest.mark.asyncio
async def test_workflow_executor_surfaces_unsent_service_outputs(loaded_plugins):
    from src.plugins.autogpt.workflow import WorkflowExecutor
    from src.plugins.autogpt.schema import WorkflowStep, AgentWorkflow, CommandObservation

    async def dispatch(task):
        return [
            CommandObservation(
                trace_id="autogpt-service-output",
                command=task.command,
                success=True,
                message="命令已通过统一执行器完成。",
                outputs=["用户信息：你是教师用户。"],
                context_outputs=["当前用户已绑定教师身份。"],
                outputs_sent_to_user=False,
            )
        ]

    workflow = AgentWorkflow(
        trace_id="autogpt-service-output",
        kind="command",
        goal="查询我的信息",
        steps=[WorkflowStep(step_id="step-1", title="执行命令：我的信息", command="我的信息")],
    )

    execution = await WorkflowExecutor(dispatch).execute(workflow)

    assert execution.workflow.status == "completed"
    assert execution.user_message == "用户信息：你是教师用户。"


def test_format_execution_status_counts_completed_commands(loaded_plugins):
    from src.plugins.autogpt.workflow import format_execution_status
    from src.plugins.autogpt.schema import WorkflowStep, AgentWorkflow, WorkflowExecutionResult

    workflow = AgentWorkflow(
        trace_id="autogpt-status",
        kind="command_sequence",
        steps=[
            WorkflowStep(step_id="step-1", title="执行命令：我的信息", command="我的信息", status="completed"),
            WorkflowStep(step_id="step-2", title="执行命令：查询班级", command="查询班级", status="completed"),
        ],
    )

    assert format_execution_status(WorkflowExecutionResult(workflow=workflow)) == "已运行 2 条命令。"


def test_format_execution_status_marks_failed_command(loaded_plugins):
    from src.plugins.autogpt.workflow import format_execution_status
    from src.plugins.autogpt.schema import WorkflowStep, AgentWorkflow, WorkflowExecutionResult

    workflow = AgentWorkflow(
        trace_id="autogpt-status-failed",
        kind="command_sequence",
        steps=[
            WorkflowStep(step_id="step-1", title="执行命令：我的信息", command="我的信息", status="completed"),
            WorkflowStep(step_id="step-2", title="执行命令：查询班级", command="查询班级", status="failed"),
        ],
    )

    assert (
        format_execution_status(WorkflowExecutionResult(workflow=workflow))
        == "已运行 2 条命令，其中 `查询班级` 没有完成。"
    )


@pytest.mark.asyncio
async def test_workflow_executor_stops_on_failed_step(loaded_plugins):
    from src.plugins.autogpt.workflow import WorkflowExecutor
    from src.plugins.autogpt.schema import Param, WorkflowStep, AgentWorkflow, CommandObservation

    calls: list[str] = []

    async def dispatch(task):
        calls.append(task.command)
        success = task.command != "创建通知"
        return [
            CommandObservation(
                trace_id="autogpt-failed",
                command=task.command,
                params=task.params,
                success=success,
                message="命令投递失败：network error" if not success else "命令已投递给 NoneBot 事件系统。",
            )
        ]

    workflow = AgentWorkflow(
        trace_id="autogpt-failed",
        kind="command_sequence",
        goal="先创建班级再发送通知",
        steps=[
            WorkflowStep(
                step_id="step-1",
                title="执行命令：添加班级",
                command="添加班级",
                params=[Param(type="text", value="一班")],
            ),
            WorkflowStep(
                step_id="step-2",
                title="执行命令：创建通知",
                command="创建通知",
                params=[Param(type="text", value="明天收作业")],
            ),
            WorkflowStep(step_id="step-3", title="执行命令：查询通知", command="查询通知", params=[]),
        ],
    )

    execution = await WorkflowExecutor(dispatch).execute(workflow)

    assert calls == ["添加班级", "创建通知"]
    assert execution.workflow.status == "failed"
    assert [step.status for step in execution.workflow.steps] == ["completed", "failed", "pending"]
    assert execution.user_message is not None
    assert [event.event_type for event in execution.workflow.events] == [
        "workflow_started",
        "step_started",
        "step_completed",
        "step_started",
        "step_failed",
        "workflow_failed",
    ]
