from datetime import datetime
from collections import Counter
from typing import Callable, Awaitable

from nonebot import logger

from .command_tools import CommandToolCatalog
from .playbooks import WorkflowPlaybook, WorkflowPlaybookStep, playbook_catalog
from .schema import (
    AutoTask,
    AgentPlan,
    RiskLevel,
    IntentRoute,
    AutoTaskList,
    WorkflowKind,
    WorkflowStep,
    TaskWorkflow,
    WorkflowStatus,
    AgentTurnResult,
    WorkflowApproval,
    CommandObservation,
    WorkflowExecutionResult,
    AgentObservabilityMetrics,
)

WorkflowDispatcher = Callable[[AutoTask], Awaitable[list[CommandObservation]]]


class WorkflowObservabilityBuilder:
    """为工作流准备独立可观测指标快照。"""

    @staticmethod
    def build(trace_id: str, observability: AgentObservabilityMetrics | None) -> AgentObservabilityMetrics:
        """复制当前轮次指标，避免后续执行阶段污染输入快照。"""

        if observability is None:
            return AgentObservabilityMetrics(trace_id=trace_id)
        snapshot = observability.copy(deep=True)
        snapshot.trace_id = trace_id
        return snapshot


class WorkflowKindResolver:
    """根据路由、计划和任务结果解析工作流基础语义。"""

    @staticmethod
    def infer_kind(route: IntentRoute | None, auto_tasks: AutoTaskList | None) -> WorkflowKind:
        """推断工作流类型。"""

        if auto_tasks and auto_tasks.is_violation:
            return "violation"
        if auto_tasks and auto_tasks.need_confirm:
            return "clarification"
        if auto_tasks and len(auto_tasks.tasks) > 1:
            return "command_sequence"
        if auto_tasks and auto_tasks.tasks:
            return "command"
        if route and route.requires_rag:
            return "knowledge"
        return "chat"

    @staticmethod
    def infer_status(plan: AgentPlan | None, auto_tasks: AutoTaskList | None) -> WorkflowStatus:
        """推断工作流初始状态。"""

        if auto_tasks and auto_tasks.need_confirm:
            return "needs_confirm"
        if plan and plan.confirmation_question:
            return "needs_confirm"
        return "planned"

    @staticmethod
    def build_goal(route: IntentRoute | None, plan: AgentPlan | None, auto_tasks: AutoTaskList | None) -> str:
        """生成工作流目标。"""

        if plan and plan.goal:
            return plan.goal
        if auto_tasks and auto_tasks.reply:
            return auto_tasks.reply
        if route and route.reply:
            return route.reply
        return ""

    @staticmethod
    def build_summary(
        route: IntentRoute | None,
        auto_tasks: AutoTaskList | None,
        playbook: WorkflowPlaybook | None,
    ) -> str:
        """生成工作流摘要。"""

        if playbook:
            return f"命中工作流模板：{playbook.name}。"
        if auto_tasks and auto_tasks.tasks:
            commands = " -> ".join(task.command for task in auto_tasks.tasks)
            return f"按顺序执行项目命令: {commands}"
        if auto_tasks and auto_tasks.need_confirm:
            return auto_tasks.reply or "当前任务仍需向用户确认。"
        if route and route.requires_rag:
            return "当前轮次需要知识检索支持。"
        return (auto_tasks.reply if auto_tasks else None) or (route.reply if route else None) or "普通对话回复。"

    @staticmethod
    def build_reason(route: IntentRoute | None, plan: AgentPlan | None) -> str:
        """生成工作流原因说明。"""

        if plan and plan.reason:
            return plan.reason
        if route:
            return route.reason
        return ""


class WorkflowStepBuilder:
    """把 AutoTask 序列转换为可执行工作流步骤。"""

    @classmethod
    def build(
        cls,
        auto_tasks: AutoTaskList | None,
        command_tools: CommandToolCatalog,
        playbook: WorkflowPlaybook | None,
    ) -> list[WorkflowStep]:
        """构建工作流步骤列表。"""

        if auto_tasks is None:
            return []

        steps: list[WorkflowStep] = []
        playbook_steps = list(playbook.steps) if playbook else []
        for index, task in enumerate(auto_tasks.tasks, start=1):
            tool = command_tools.get(task.command)
            matched_playbook_step = cls.match_playbook_step(task.command, playbook_steps)
            steps.append(
                WorkflowStep(
                    step_id=f"step-{index}",
                    title=matched_playbook_step.title if matched_playbook_step else f"执行命令：{task.command}",
                    command=task.command,
                    params=list(task.params),
                    description=(
                        matched_playbook_step.description
                        if matched_playbook_step
                        else (tool.description if tool else "") or "通过统一 service 命令执行项目能力。"
                    ),
                    risk_level=tool.risk_level if tool else "medium",
                )
            )
        return steps

    @staticmethod
    def match_playbook(auto_tasks: AutoTaskList | None) -> WorkflowPlaybook | None:
        """根据命令序列匹配稳定工作流模板。"""

        if auto_tasks is None or not auto_tasks.tasks:
            return None
        commands = [task.command for task in auto_tasks.tasks]
        return playbook_catalog.match_commands(commands)

    @staticmethod
    def match_playbook_step(command: str, playbook_steps: list[WorkflowPlaybookStep]) -> WorkflowPlaybookStep | None:
        """从模板步骤中取出当前命令对应的步骤说明。"""

        for index, step in enumerate(playbook_steps):
            if step.command == command:
                del playbook_steps[index]
                return step
        return None


class WorkflowApprovalBuilder:
    """根据风险、缺失信息和用户确认意图构建审批语义。"""

    @classmethod
    def build(
        cls,
        route: IntentRoute | None,
        plan: AgentPlan | None,
        auto_tasks: AutoTaskList | None,
        steps: list[WorkflowStep],
    ) -> WorkflowApproval:
        """构建工作流级审批状态。"""

        prompt = cls.build_prompt(route, plan, auto_tasks)
        risk_level = cls.resolve_risk_level(plan, steps)
        missing_info = list(plan.missing_info) if plan else []

        if missing_info:
            return WorkflowApproval(
                required=True,
                type="missing_info",
                status="pending",
                reason="执行前仍缺少必要信息，需要先向用户确认或补充参数。",
                prompt=prompt,
                missing_info=missing_info,
                risk_level=risk_level,
            )

        needs_confirm = bool((route and route.need_confirm) or (auto_tasks and auto_tasks.need_confirm))
        has_high_risk_step = any(step.risk_level == "high" for step in steps)
        if needs_confirm or (plan and plan.confirmation_question):
            approval_type = "high_risk" if risk_level == "high" or has_high_risk_step else "user_confirm"
            reason = (
                "该任务包含高风险步骤，执行前需要用户确认。"
                if approval_type == "high_risk"
                else "当前任务在执行前需要用户确认。"
            )
            return WorkflowApproval(
                required=True,
                type=approval_type,
                status="pending",
                reason=reason,
                prompt=prompt,
                risk_level=risk_level,
            )

        return WorkflowApproval(required=False, type="none", status="not_required", risk_level=risk_level)

    @staticmethod
    def build_prompt(route: IntentRoute | None, plan: AgentPlan | None, auto_tasks: AutoTaskList | None) -> str:
        """解析面向用户的确认提示。"""

        return (
            (plan.confirmation_question if plan and plan.confirmation_question else None)
            or (auto_tasks.reply if auto_tasks and auto_tasks.need_confirm else None)
            or (route.reply if route and route.need_confirm else None)
            or ""
        )

    @staticmethod
    def resolve_risk_level(plan: AgentPlan | None, steps: list[WorkflowStep]) -> RiskLevel:
        """解析工作流整体风险等级。"""

        if plan:
            return plan.risk_level
        return "high" if any(step.risk_level == "high" for step in steps) else "low"

    @staticmethod
    def apply_to_steps(steps: list[WorkflowStep], approval: WorkflowApproval) -> None:
        """把工作流级审批结果映射到步骤级元数据。"""

        if approval.type != "high_risk":
            return
        for step in steps:
            if step.risk_level != "high":
                continue
            step.approval = WorkflowApproval(
                required=True,
                type="high_risk",
                status=approval.status,
                reason="该步骤风险较高，需要在工作流执行前获得确认。",
                prompt=approval.prompt,
                risk_level=step.risk_level,
            )


class WorkflowBuilder:
    """把本轮 AI 规划结果转换成显式工作流。"""

    kind_resolver = WorkflowKindResolver()
    step_builder = WorkflowStepBuilder()
    approval_builder = WorkflowApprovalBuilder()
    observability_builder = WorkflowObservabilityBuilder()

    @classmethod
    def build(
        cls,
        trace_id: str,
        route: IntentRoute | None,
        plan: AgentPlan | None,
        auto_tasks: AutoTaskList | None,
        command_tools: CommandToolCatalog,
        observability: AgentObservabilityMetrics | None = None,
    ) -> TaskWorkflow | None:
        """根据路由、计划和自动任务结果构建工作流。"""

        if route is None and plan is None and auto_tasks is None:
            return None

        playbook = cls.step_builder.match_playbook(auto_tasks)
        steps = cls.step_builder.build(auto_tasks, command_tools, playbook)
        approval = cls.approval_builder.build(route, plan, auto_tasks, steps)
        cls.approval_builder.apply_to_steps(steps, approval)
        workflow = TaskWorkflow(
            trace_id=trace_id,
            kind=cls.kind_resolver.infer_kind(route, auto_tasks),
            status=cls.kind_resolver.infer_status(plan, auto_tasks),
            goal=cls.kind_resolver.build_goal(route, plan, auto_tasks),
            summary=cls.kind_resolver.build_summary(route, auto_tasks, playbook),
            reason=cls.kind_resolver.build_reason(route, plan),
            playbook_id=playbook.playbook_id if playbook else None,
            playbook_name=playbook.name if playbook else None,
            requires_rag=bool((route and route.requires_rag) or (plan and plan.requires_rag)),
            requires_command=bool(
                (route and route.requires_command)
                or (plan and plan.requires_command)
                or (auto_tasks and auto_tasks.tasks)
            ),
            need_confirm=approval.required,
            approval=approval,
            missing_info=list(plan.missing_info) if plan else [],
            steps=steps,
            observability=cls.observability_builder.build(trace_id, observability),
        )
        workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status=workflow.status)
        cls.fill_final_hit_commands(workflow, command_tools)
        if approval.required:
            workflow.add_event(
                "approval_requested",
                approval.reason or "当前工作流需要用户确认。",
                status=approval.status,
            )
        return workflow

    @classmethod
    def fill_final_hit_commands(cls, workflow: TaskWorkflow, command_tools: CommandToolCatalog) -> None:
        """为跳过校验节点的确定性命令路径补齐最终命中记录。"""

        if workflow.observability.final_hit_commands:
            return
        commands = cls.resolve_final_hit_commands(workflow.steps, command_tools)
        if commands:
            workflow.observability.final_hit_commands = commands

    @staticmethod
    def resolve_final_hit_commands(
        steps: list[WorkflowStep],
        command_tools: CommandToolCatalog,
    ) -> list[str]:
        """从最终工作流步骤中提取仍存在于命令目录的命令。"""

        commands: list[str] = []
        for step in steps:
            if step.step_type != "command" or not step.command:
                continue
            tool = command_tools.get(step.command)
            if tool is None:
                continue
            commands.append(tool.command)
        return commands


class WorkflowExecutor:
    """顺序执行显式工作流，复用统一 service 命令链路。"""

    def __init__(self, dispatcher: WorkflowDispatcher) -> None:
        self.dispatcher = dispatcher

    async def execute(self, workflow: TaskWorkflow) -> WorkflowExecutionResult:
        """执行工作流中的命令步骤。"""

        if workflow.need_confirm or workflow.status == "needs_confirm":
            workflow.add_event("approval_requested", "工作流仍在等待用户确认，暂不执行。", status="pending")
            logger.info(f'AutoGPT trace "{workflow.trace_id}" workflow requires confirmation before execution')
            return WorkflowExecutionResult(workflow=workflow, observability=workflow.observability)

        if not workflow.steps:
            workflow.status = "completed"
            workflow.finished_at = datetime.now()
            workflow.add_event("workflow_started", "工作流没有可执行步骤，直接结束。", status="completed")
            workflow.add_event("workflow_completed", "工作流已完成。", status="completed")
            update_execution_metrics(workflow, [])
            return WorkflowExecutionResult(workflow=workflow, observability=workflow.observability)

        workflow.status = "running"
        workflow.started_at = datetime.now()
        workflow.add_event("workflow_started", "工作流开始执行。", status="running")
        result = WorkflowExecutionResult(workflow=workflow, observability=workflow.observability)

        for step in workflow.steps:
            if step.step_type != "command":
                result = self.handle_non_command_step(workflow, step, result)
                if workflow.status in {"needs_confirm", "failed"}:
                    update_execution_metrics(workflow, result.observations)
                    result.observability = workflow.observability
                    return result
                continue

            step.status = "running"
            step.started_at = datetime.now()
            workflow.add_event(
                "step_started",
                f"步骤「{step.title}」开始执行。",
                step_id=step.step_id,
                command=step.command,
                status="running",
            )
            task = AutoTask(command=step.command, params=list(step.params))
            logger.info(
                'AutoGPT trace "{}" workflow step "{}" dispatching command "{}"'.format(
                    workflow.trace_id,
                    step.step_id,
                    step.command,
                )
            )
            observations = await self.dispatcher(task)
            result.observations.extend(observations)

            failed_observation = next((observation for observation in observations if not observation.success), None)
            if failed_observation:
                step.status = "failed"
                step.observation_message = failed_observation.message
                step.finished_at = datetime.now()
                workflow.status = "failed"
                workflow.finished_at = datetime.now()
                workflow.add_event(
                    "step_failed",
                    failed_observation.message,
                    step_id=step.step_id,
                    command=step.command,
                    status="failed",
                )
                workflow.add_event("workflow_failed", failed_observation.message, status="failed")
                unsent_outputs = collect_unsent_observation_outputs(observations)
                result.raw_outputs = unsent_outputs
                result.user_message = (
                    "\n\n".join(unsent_outputs)
                    if unsent_outputs
                    else "我执行到一半出现了问题，有些步骤可能没有完成，请稍后重试或分步执行。"
                )
                update_execution_metrics(workflow, result.observations)
                result.observability = workflow.observability
                return result

            step.status = "completed"
            step.observation_message = "命令已通过统一 service 执行器完成。"
            step.finished_at = datetime.now()
            workflow.add_event(
                "step_completed",
                step.observation_message,
                step_id=step.step_id,
                command=step.command,
                status="completed",
            )

        workflow.status = "completed"
        workflow.finished_at = datetime.now()
        workflow.add_event("workflow_completed", "工作流已完成。", status="completed")
        unsent_outputs = collect_unsent_observation_outputs(result.observations)
        result.raw_outputs = unsent_outputs
        if unsent_outputs:
            result.user_message = "\n\n".join(unsent_outputs)
        update_execution_metrics(workflow, result.observations)
        result.observability = workflow.observability
        return result

    def handle_non_command_step(
        self,
        workflow: TaskWorkflow,
        step: WorkflowStep,
        result: WorkflowExecutionResult,
    ) -> WorkflowExecutionResult:
        """处理第一版暂不直接执行的非命令任务流步骤。"""

        step.started_at = datetime.now()
        if step.step_type == "confirm":
            step.status = "pending"
            workflow.need_confirm = True
            workflow.status = "needs_confirm"
            workflow.add_event(
                "approval_requested",
                step.description or step.title or "任务流需要用户确认后继续执行。",
                step_id=step.step_id,
                status="pending",
            )
            result.user_message = step.description or step.title or "这个操作需要你确认后我再继续。"
            return result

        step.status = "failed"
        step.finished_at = datetime.now()
        workflow.status = "failed"
        workflow.finished_at = datetime.now()
        message = f"任务流步骤类型 `{step.step_type}` 当前尚未接入执行器。"
        step.observation_message = message
        workflow.add_event("step_failed", message, step_id=step.step_id, status="failed")
        workflow.add_event("workflow_failed", message, status="failed")
        result.user_message = message
        return result


def build_turn_result(
    trace_id: str,
    route: IntentRoute | None,
    plan: AgentPlan | None,
    auto_tasks: AutoTaskList | None,
    command_tools: CommandToolCatalog,
    observability: AgentObservabilityMetrics | None = None,
) -> AgentTurnResult:
    """组装本轮处理结果，供入口层和会话层统一消费。"""

    workflow = WorkflowBuilder.build(
        trace_id=trace_id,
        route=route,
        plan=plan,
        auto_tasks=auto_tasks,
        command_tools=command_tools,
        observability=observability,
    )
    metrics = workflow.observability if workflow is not None else AgentObservabilityMetrics(trace_id=trace_id)
    return AgentTurnResult(
        route=route,
        plan=plan,
        auto_tasks=auto_tasks,
        workflow=workflow,
        observability=metrics,
    )


def workflow_to_auto_tasks(workflow: TaskWorkflow, reply: str | None = None) -> AutoTaskList:
    """把显式工作流重新投影为兼容当前入口的自动任务结果。"""

    return AutoTaskList(
        reply=reply,
        tasks=[AutoTask(command=step.command, params=list(step.params)) for step in workflow.steps],
        need_confirm=workflow.need_confirm,
    )


def clone_workflow_for_execution(workflow: TaskWorkflow, trace_id: str) -> TaskWorkflow:
    """复制并重置一个待确认工作流，供用户确认后重新执行。"""

    cloned = workflow.copy(deep=True)
    cloned.source_trace_id = workflow.trace_id
    cloned.trace_id = trace_id
    cloned.status = "planned"
    cloned.need_confirm = False
    if cloned.approval.required:
        cloned.approval.status = "approved"
        cloned.add_event("approval_approved", "用户已确认，工作流可以继续执行。", status="approved")
    cloned.add_event("workflow_resumed", "待确认工作流已恢复执行。", status="planned")
    cloned.started_at = None
    cloned.finished_at = None
    for step in cloned.steps:
        step.status = "pending"
        step.observation_message = ""
        step.started_at = None
        step.finished_at = None
        if step.approval.required:
            step.approval.status = "approved"
    return cloned


def workflow_requires_confirmation(workflow: TaskWorkflow) -> bool:
    """判断当前工作流是否属于“待确认后可直接执行”的状态。"""

    return workflow.need_confirm and bool(workflow.steps)


def collect_unsent_observation_outputs(observations: list[CommandObservation]) -> list[str]:
    """收集尚未发给用户的命令可见输出，避免 service-style 命令静默完成。"""

    outputs: list[str] = []
    seen: set[str] = set()
    for observation in observations:
        if observation.outputs_sent_to_user:
            continue
        for output in observation.outputs:
            text = output.strip()
            if not text or text in seen:
                continue
            outputs.append(text)
            seen.add(text)
    return outputs


def update_execution_metrics(workflow: TaskWorkflow, observations: list[CommandObservation]) -> None:
    """根据命令执行观察结果回填重复调用等执行指标。"""

    executed_commands = [observation.command for observation in observations if observation.dispatch_type == "command"]
    repeated_commands = [command for command, count in Counter(executed_commands).items() if count > 1]
    workflow.observability.trace_id = workflow.trace_id
    workflow.observability.execution.executed_commands = executed_commands
    workflow.observability.execution.repeated_invocation = bool(repeated_commands)
    workflow.observability.execution.repeated_commands = repeated_commands


def format_execution_status(execution: WorkflowExecutionResult) -> str:
    """生成面向用户的简洁命令执行状态。"""

    steps = execution.workflow.steps
    if not steps:
        return ""

    completed = sum(1 for step in steps if step.status == "completed")
    failed = sum(1 for step in steps if step.status == "failed")
    attempted = completed + failed
    if attempted <= 0:
        return ""

    if failed:
        failed_step = next((step for step in steps if step.status == "failed"), None)
        failed_title = failed_step.command if failed_step else "某个命令"
        return f"已运行 {attempted} 条命令，其中 `{failed_title}` 没有完成。"
    return f"已运行 {attempted} 条命令。"
