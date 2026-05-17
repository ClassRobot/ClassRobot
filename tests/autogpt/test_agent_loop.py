import pytest


def test_loop_budget_stops_after_verify_attempt_limit(loaded_plugins):
    from core.agent.runtime.loop import LoopBudget, AgentLoopConfig, AgentLoopDecision

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
    from core.agent.runtime.loop import ObservationInterpreter
    from core.agent.runtime.schema import Param, CommandObservation

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


@pytest.mark.asyncio
async def test_cognitive_loop_stops_after_max_steps(loaded_plugins):
    from core.agent.runtime.loop import CognitiveAgentLoop, AgentLoopConfig
    from core.agent.runtime.schema import WorkflowStep, TaskWorkflow, CommandObservation

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
    from core.agent.runtime.loop import CognitiveAgentLoop, AgentLoopConfig
    from core.agent.runtime.schema import WorkflowStep, TaskWorkflow, CommandObservation

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
    from utils.helper import Helpers
    from core.agent.runtime.loop import CognitiveAgentLoop, AgentLoopConfig, AgentLoopDecision
    from core.agent.runtime.schema import Param, WorkflowStep, TaskWorkflow, CommandObservation
    from core.agent.runtime.command_tools import CommandToolCatalog
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
    from core.agent.runtime.loop import CognitiveAgentLoop, AgentLoopConfig, AgentLoopDecision
    from core.agent.runtime.schema import WorkflowStep, TaskWorkflow

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
