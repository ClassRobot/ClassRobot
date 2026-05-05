from datetime import datetime
from typing import Awaitable, Callable

from nonebot import logger

from .schema import (
    AutoTask,
    AgentPlan,
    AutoTaskList,
    WorkflowApproval,
    AgentTurnResult,
    AgentWorkflow,
    CommandObservation,
    IntentRoute,
    WorkflowExecutionResult,
    WorkflowStep,
)
from .command_tools import CommandToolCatalog
from .playbooks import WorkflowPlaybook, WorkflowPlaybookStep, playbook_catalog

WorkflowDispatcher = Callable[[AutoTask], Awaitable[list[CommandObservation]]]


class WorkflowBuilder:
    """把本轮 AI 规划结果转换成显式工作流。"""

    @classmethod
    def build(
        cls,
        trace_id: str,
        route: IntentRoute | None,
        plan: AgentPlan | None,
        auto_tasks: AutoTaskList | None,
        command_tools: CommandToolCatalog,
    ) -> AgentWorkflow | None:
        """根据路由、计划和自动任务结果构建工作流。"""

        if route is None and plan is None and auto_tasks is None:
            return None

        playbook = cls._match_playbook(auto_tasks)
        steps = cls._build_steps(auto_tasks, command_tools, playbook)
        approval = cls._build_approval(route, plan, auto_tasks, steps)
        cls._apply_step_approval(steps, approval)
        workflow = AgentWorkflow(
            trace_id=trace_id,
            kind=cls._infer_kind(route, auto_tasks),
            status=cls._infer_status(plan, auto_tasks),
            goal=cls._build_goal(route, plan, auto_tasks),
            summary=cls._build_summary(route, plan, auto_tasks, playbook),
            reason=cls._build_reason(route, plan),
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
        )
        workflow.add_event("workflow_created", "本轮消息已提升为显式工作流。", status=workflow.status)
        if approval.required:
            workflow.add_event(
                "approval_requested",
                approval.reason or "当前工作流需要用户确认。",
                status=approval.status,
            )
        return workflow

    @staticmethod
    def _infer_kind(route: IntentRoute | None, auto_tasks: AutoTaskList | None) -> str:
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
    def _infer_status(plan: AgentPlan | None, auto_tasks: AutoTaskList | None) -> str:
        if auto_tasks and auto_tasks.need_confirm:
            return "needs_confirm"
        if plan and plan.confirmation_question:
            return "needs_confirm"
        return "planned"

    @staticmethod
    def _build_goal(route: IntentRoute | None, plan: AgentPlan | None, auto_tasks: AutoTaskList | None) -> str:
        if plan and plan.goal:
            return plan.goal
        if auto_tasks and auto_tasks.reply:
            return auto_tasks.reply
        if route and route.reply:
            return route.reply
        return ""

    @staticmethod
    def _build_summary(
        route: IntentRoute | None,
        plan: AgentPlan | None,
        auto_tasks: AutoTaskList | None,
        playbook: WorkflowPlaybook | None,
    ) -> str:
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
    def _build_reason(route: IntentRoute | None, plan: AgentPlan | None) -> str:
        if plan and plan.reason:
            return plan.reason
        if route:
            return route.reason
        return ""

    @classmethod
    def _build_steps(
        cls,
        auto_tasks: AutoTaskList | None,
        command_tools: CommandToolCatalog,
        playbook: WorkflowPlaybook | None,
    ) -> list[WorkflowStep]:
        if auto_tasks is None:
            return []

        steps: list[WorkflowStep] = []
        playbook_steps = list(playbook.steps) if playbook else []
        for index, task in enumerate(auto_tasks.tasks, start=1):
            tool = command_tools.get(task.command)
            matched_playbook_step = cls._match_playbook_step(task.command, playbook_steps)
            steps.append(
                WorkflowStep(
                    step_id=f"step-{index}",
                    title=matched_playbook_step.title if matched_playbook_step else f"执行命令：{task.command}",
                    command=task.command,
                    params=list(task.params),
                    description=(
                        matched_playbook_step.description
                        if matched_playbook_step
                        else (tool.description if tool else "") or "通过 NoneBot 命令系统执行既有项目能力。"
                    ),
                    risk_level=tool.risk_level if tool else "medium",
                )
            )
        return steps

    @staticmethod
    def _build_approval(
        route: IntentRoute | None,
        plan: AgentPlan | None,
        auto_tasks: AutoTaskList | None,
        steps: list[WorkflowStep],
    ) -> WorkflowApproval:
        prompt = (
            (plan.confirmation_question if plan and plan.confirmation_question else None)
            or (auto_tasks.reply if auto_tasks and auto_tasks.need_confirm else None)
            or (route.reply if route and route.need_confirm else None)
            or ""
        )
        risk_level = (
            plan.risk_level if plan else ("high" if any(step.risk_level == "high" for step in steps) else "low")
        )
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
    def _apply_step_approval(steps: list[WorkflowStep], approval: WorkflowApproval) -> None:
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

    @staticmethod
    def _match_playbook(auto_tasks: AutoTaskList | None) -> WorkflowPlaybook | None:
        if auto_tasks is None or not auto_tasks.tasks:
            return None
        commands = [task.command for task in auto_tasks.tasks]
        return playbook_catalog.match_commands(commands)

    @staticmethod
    def _match_playbook_step(command: str, playbook_steps: list[WorkflowPlaybookStep]) -> WorkflowPlaybookStep | None:
        for index, step in enumerate(playbook_steps):
            if step.command == command:
                del playbook_steps[index]
                return step
        return None


class WorkflowExecutor:
    """顺序执行显式工作流，复用当前项目命令投递链路。"""

    def __init__(self, dispatcher: WorkflowDispatcher) -> None:
        self.dispatcher = dispatcher

    async def execute(self, workflow: AgentWorkflow) -> WorkflowExecutionResult:
        """执行工作流中的命令步骤。"""

        if workflow.need_confirm or workflow.status == "needs_confirm":
            workflow.add_event("approval_requested", "工作流仍在等待用户确认，暂不执行。", status="pending")
            logger.info(f'AutoGPT trace "{workflow.trace_id}" workflow requires confirmation before execution')
            return WorkflowExecutionResult(workflow=workflow)

        if not workflow.steps:
            workflow.status = "completed"
            workflow.finished_at = datetime.now()
            workflow.add_event("workflow_started", "工作流没有可执行步骤，直接结束。", status="completed")
            workflow.add_event("workflow_completed", "工作流已完成。", status="completed")
            return WorkflowExecutionResult(workflow=workflow)

        workflow.status = "running"
        workflow.started_at = datetime.now()
        workflow.add_event("workflow_started", "工作流开始执行。", status="running")
        result = WorkflowExecutionResult(workflow=workflow)

        for step in workflow.steps:
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
                result.user_message = (
                    "\n\n".join(unsent_outputs)
                    if unsent_outputs
                    else "我执行到一半出现了问题，有些步骤可能没有完成，请稍后重试或分步执行。"
                )
                return result

            step.status = "completed"
            step.observation_message = "命令已按既有 NoneBot 链路完成投递。"
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
        if unsent_outputs:
            result.user_message = "\n\n".join(unsent_outputs)
        return result


def build_turn_result(
    trace_id: str,
    route: IntentRoute | None,
    plan: AgentPlan | None,
    auto_tasks: AutoTaskList | None,
    command_tools: CommandToolCatalog,
) -> AgentTurnResult:
    """组装本轮处理结果，供入口层和会话层统一消费。"""

    workflow = WorkflowBuilder.build(
        trace_id=trace_id,
        route=route,
        plan=plan,
        auto_tasks=auto_tasks,
        command_tools=command_tools,
    )
    return AgentTurnResult(route=route, plan=plan, auto_tasks=auto_tasks, workflow=workflow)


def workflow_to_auto_tasks(workflow: AgentWorkflow, reply: str | None = None) -> AutoTaskList:
    """把显式工作流重新投影为兼容当前入口的自动任务结果。"""

    return AutoTaskList(
        reply=reply,
        tasks=[AutoTask(command=step.command, params=list(step.params)) for step in workflow.steps],
        need_confirm=workflow.need_confirm,
    )


def clone_workflow_for_execution(workflow: AgentWorkflow, trace_id: str) -> AgentWorkflow:
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


def workflow_requires_confirmation(workflow: AgentWorkflow) -> bool:
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
