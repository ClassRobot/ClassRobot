from typing import Literal
from datetime import datetime

from pydantic import Field, BaseModel
from utils.llm.message import Content
from nonebot_plugin_alconna import UniMessage
from utils.llm.util import uni_message_to_contents
from utils.schemas.auto_task import Param as Param  # noqa
from utils.schemas.auto_task import AutoTask as AutoTask  # noqa
from utils.schemas.auto_task import AutoTaskList as AutoTaskList  # noqa


class IntentRoute(BaseModel):
    """AutoGPT 对当前消息的入口路由判断。"""

    intent: Literal["chat", "knowledge", "command", "complex_task", "vision_file", "violation"] = "chat"
    """当前消息的主要意图类型。"""
    reply: str | None = None
    """可以直接回复用户时填写。"""
    requires_rag: bool = False
    """是否需要检索知识库。"""
    requires_command: bool = False
    """是否需要规划并调用项目命令。"""
    need_confirm: bool = False
    """是否需要用户补充信息或确认。"""
    reason: str = ""
    """简短说明路由原因，供日志和调试使用。"""


class AgentPlan(BaseModel):
    """AutoGPT 对当前任务的显式执行计划。"""

    goal: str = ""
    """用户最终想完成的目标。"""
    facts: list[str] = []
    """已经确认的事实。"""
    missing_info: list[str] = []
    """执行前仍缺少的信息。"""
    risk_level: Literal["low", "medium", "high"] = "low"
    """计划风险等级。"""
    requires_rag: bool = False
    """是否需要知识检索。"""
    requires_command: bool = False
    """是否需要调用项目命令。"""
    should_execute: bool = False
    """当前是否可以直接执行命令。"""
    candidate_commands: list[str] = []
    """可能要调用的项目命令名称。"""
    steps: list[str] = []
    """面向系统的执行步骤。"""
    confirmation_question: str | None = None
    """需要向用户确认时的问题。"""
    reason: str = ""
    """简短说明计划理由。"""


WorkflowKind = Literal["chat", "knowledge", "command", "command_sequence", "clarification", "violation"]
WorkflowStatus = Literal["planned", "running", "completed", "failed", "needs_confirm", "cancelled"]
WorkflowStepStatus = Literal["pending", "running", "completed", "failed"]
RiskLevel = Literal["low", "medium", "high"]
ApprovalType = Literal["none", "user_confirm", "high_risk", "missing_info"]
ApprovalStatus = Literal["not_required", "pending", "approved", "rejected"]
WorkflowEventType = Literal[
    "workflow_created",
    "approval_requested",
    "approval_approved",
    "approval_rejected",
    "workflow_resumed",
    "workflow_started",
    "step_started",
    "step_completed",
    "step_failed",
    "workflow_completed",
    "workflow_failed",
    "workflow_cancelled",
]


class WorkflowApproval(BaseModel):
    """描述工作流或步骤上的审批语义。"""

    required: bool = False
    """该工作流或步骤是否要求审批。"""
    type: ApprovalType = "none"
    """审批类型。"""
    status: ApprovalStatus = "not_required"
    """审批当前状态。"""
    reason: str = ""
    """为什么需要审批。"""
    prompt: str = ""
    """面向用户的确认文案。"""
    missing_info: list[str] = Field(default_factory=list)
    """如果是信息不足，记录缺失的字段。"""
    risk_level: RiskLevel = "low"
    """触发审批时对应的风险等级。"""


class WorkflowEvent(BaseModel):
    """描述工作流生命周期中的离散事件。"""

    event_type: WorkflowEventType
    """事件类型。"""
    message: str
    """面向审计和调试的简要说明。"""
    step_id: str | None = None
    """如果该事件属于某个步骤，则记录步骤标识。"""
    command: str | None = None
    """如果该事件属于某个命令，则记录命令名。"""
    status: str | None = None
    """事件发生时对应的状态快照。"""
    created_at: datetime = Field(default_factory=datetime.now)
    """事件创建时间。"""


class CommandObservation(BaseModel):
    """AutoGPT 命令投递后的结构化观察记录。"""

    trace_id: str = ""
    """本轮 AutoGPT 请求的追踪 ID。"""
    command: str
    """被投递的项目命令名称。"""
    params: list[Param] = Field(default_factory=list)
    """本次随命令一起投递的参数。"""
    dispatch_type: Literal["command", "separate_param", "missing_command"] = "command"
    """投递类型：主命令、分离参数或缺失命令。"""
    success: bool = True
    """是否成功投递到 NoneBot 事件系统。"""
    message: str = ""
    """投递结果说明。"""
    created_at: datetime = Field(default_factory=datetime.now)
    """观察记录创建时间。"""


class WorkflowStep(BaseModel):
    """描述一条可被执行器顺序运行的工作流步骤。"""

    step_id: str
    """步骤唯一标识。"""
    title: str
    """面向日志和文档的步骤标题。"""
    command: str
    """步骤最终会调用的项目命令。"""
    params: list[Param] = Field(default_factory=list)
    """本步骤使用的命令参数。"""
    description: str = ""
    """步骤说明。"""
    risk_level: RiskLevel = "low"
    """步骤风险等级。"""
    approval: WorkflowApproval = Field(default_factory=WorkflowApproval)
    """该步骤的审批语义。"""
    status: WorkflowStepStatus = "pending"
    """步骤当前执行状态。"""
    observation_message: str = ""
    """执行结果说明。"""
    created_at: datetime = Field(default_factory=datetime.now)
    """步骤创建时间。"""
    started_at: datetime | None = None
    """步骤开始执行时间。"""
    finished_at: datetime | None = None
    """步骤完成时间。"""


class AgentWorkflow(BaseModel):
    """描述当前用户消息对应的显式工作流。"""

    trace_id: str = ""
    """与本轮请求对应的追踪 ID。"""
    source_trace_id: str | None = None
    """如果当前工作流由上一条待确认工作流恢复而来，记录来源 trace_id。"""
    kind: WorkflowKind = "chat"
    """工作流类型。"""
    status: WorkflowStatus = "planned"
    """工作流当前执行状态。"""
    goal: str = ""
    """用户最终目标。"""
    summary: str = ""
    """面向日志、审计和文档的简要摘要。"""
    reason: str = ""
    """生成当前工作流的原因。"""
    playbook_id: str | None = None
    """命中的工作流模板 ID。"""
    playbook_name: str | None = None
    """命中的工作流模板名称。"""
    requires_rag: bool = False
    """是否依赖知识检索。"""
    requires_command: bool = False
    """是否依赖项目命令执行。"""
    need_confirm: bool = False
    """是否需要用户进一步确认。"""
    approval: WorkflowApproval = Field(default_factory=WorkflowApproval)
    """工作流级别的审批语义。"""
    events: list[WorkflowEvent] = Field(default_factory=list)
    """工作流生命周期中的事件时间线。"""
    missing_info: list[str] = Field(default_factory=list)
    """工作流当前缺失的信息。"""
    steps: list[WorkflowStep] = Field(default_factory=list)
    """按顺序执行的工作流步骤。"""
    created_at: datetime = Field(default_factory=datetime.now)
    """工作流创建时间。"""
    started_at: datetime | None = None
    """工作流开始执行时间。"""
    finished_at: datetime | None = None
    """工作流结束时间。"""

    def add_event(
        self,
        event_type: WorkflowEventType,
        message: str,
        *,
        step_id: str | None = None,
        command: str | None = None,
        status: str | None = None,
    ) -> WorkflowEvent:
        """向工作流追加一条生命周期事件。"""

        event = WorkflowEvent(
            event_type=event_type,
            message=message,
            step_id=step_id,
            command=command,
            status=status,
        )
        self.events.append(event)
        return event


class AgentTurnResult(BaseModel):
    """统一承载一次 AutoGPT 处理的结构化结果。"""

    route: IntentRoute | None = None
    """入口路由结果。"""
    plan: AgentPlan | None = None
    """显式任务计划。"""
    auto_tasks: AutoTaskList | None = None
    """兼容现有命令调用链路的自动任务结果。"""
    workflow: AgentWorkflow | None = None
    """面向执行层的显式工作流。"""


class WorkflowExecutionResult(BaseModel):
    """描述工作流执行后的状态与观察记录。"""

    workflow: AgentWorkflow
    """执行后的工作流对象。"""
    observations: list[CommandObservation] = Field(default_factory=list)
    """顺序执行过程中产生的观察记录。"""
    user_message: str | None = None
    """需要回给用户的补充说明。"""


class ChatMessage(BaseModel):
    "用户的聊天消息"

    role: Literal["user", "help"] = "user"
    "消息角色, user: 用户, help: 帮助文档"
    user_id: int | None = None
    "用户ID"
    message: list[Content] = []
    "消息内容"
    create_at: datetime = Field(default_factory=datetime.now)
    "消息创建时间"

    def extend(self, message: UniMessage | str):
        """扩展当前集合。

        参数:
            message (UniMessage | str): 消息对象。
        """
        self.message.extend(uni_message_to_contents(message))
        return self.message
