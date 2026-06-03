from datetime import datetime
from typing import Any, Literal
from dataclasses import field, dataclass

from pydantic import Field, BaseModel
from src.core.llm.message import Content
from nonebot_plugin_alconna import UniMessage
from src.core.llm.util import uni_message_to_contents
from src.core.agent.runtime.auto_task import Param as Param  # noqa
from src.core.agent.runtime.auto_task import AutoTask as AutoTask  # noqa
from src.core.agent.runtime.auto_task import AutoTaskList as AutoTaskList  # noqa

from .capabilities import CapabilityRequirement, CapabilityFailureReason

KnowledgeSource = Literal[
    "user_chat_history",
    "group_chat_history",
    "user_file_space",
    "group_file_space",
    "external_rag",
]
KnowledgeSourceStatus = Literal["hit", "miss", "skipped", "error"]
KnowledgeSourceConfidence = Literal["high", "medium", "low", "none"]
ToolObservationSource = Literal[
    "command",
    "mcp_tool",
    "local_knowledge",
    "external_rag",
    "skill",
    "schedule",
    "unknown",
]
ToolObservationStatus = Literal["succeeded", "failed", "skipped", "partial"]
ToolObservationRelevance = Literal["unknown", "high", "medium", "low", "none"]
ToolObservationAnswerQuality = Literal["unknown", "complete", "partial", "insufficient", "failed"]


class KnowledgeSourceRequest(BaseModel):
    """描述入口路由阶段由模型选择的受控知识来源。"""

    source: KnowledgeSource
    """要检索的知识来源。"""
    query: str = ""
    """面向该知识来源的检索问题。"""
    reason: str = ""
    """为什么当前问题需要该来源。"""
    required: bool = False
    """该来源是否必须命中才能可靠回答。"""


class KnowledgeSourceObservation(BaseModel):
    """描述一次知识源检索后的结构化观察结果。"""

    source: KnowledgeSource
    """实际处理的知识来源。"""
    query: str = ""
    """实际使用的检索问题。"""
    status: KnowledgeSourceStatus = "miss"
    """检索状态。"""
    summary: str = ""
    """可直接进入 Agent 上下文的简短摘要。"""
    confidence: KnowledgeSourceConfidence = "none"
    """检索结果可信度。"""
    items_count: int = 0
    """粗略命中条目数量。"""
    required: bool = False
    """该来源是否由路由器标记为必须命中。"""


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
    knowledge_sources: list[KnowledgeSourceRequest] = Field(default_factory=list)
    """由入口路由器按语义选择的知识来源，代码层会继续做权限和范围校验。"""
    capability_requirements: list[CapabilityRequirement] = Field(default_factory=list)
    """当前目标需要的能力类型，供运行时做能力可用性校验。"""
    unavailable_reason: CapabilityFailureReason | None = None
    """如果能力不可用，记录标准失败原因。"""


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
    candidate_skills: list[str] = []
    """可能要使用的项目内 Skill 名称。"""
    candidate_mcp_tools: list[str] = []
    """可能要调用的远端 MCP tool 名称。"""
    capability_requirements: list[CapabilityRequirement] = Field(default_factory=list)
    """Planner 对本轮目标所需能力的结构化判断。"""
    unavailable_reason: CapabilityFailureReason | None = None
    """如果当前能力不足，记录标准失败原因。"""
    steps: list[str] = []
    """面向系统的执行步骤。"""
    confirmation_question: str | None = None
    """需要向用户确认时的问题。"""
    reason: str = ""
    """简短说明计划理由。"""


RuntimeScene = Literal["chat", "command", "knowledge", "vision", "task", "violation"]
TaskWorkflowStepType = Literal["command", "mcp_tool", "skill", "confirm", "respond", "schedule"]
ObservabilityStage = Literal["route", "extract", "plan", "task"]
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


class PromptStageMetric(BaseModel):
    """记录单个 Prompt 阶段的输入规模与能力召回情况。"""

    stage: ObservabilityStage
    """阶段名称，例如 route、extract、plan 或 task。"""
    prompt_char_length: int = 0
    """送入模型前的 Prompt 总长度。"""
    recalled_commands: list[str] = Field(default_factory=list)
    """当前阶段召回给模型看的命令列表。"""
    recalled_command_count: int = 0
    """当前阶段召回的命令数量。"""
    recalled_skills: list[str] = Field(default_factory=list)
    """当前阶段召回给模型看的 Skill 列表。"""
    recalled_skill_count: int = 0
    """当前阶段召回的 Skill 数量。"""
    selected_commands: list[str] = Field(default_factory=list)
    """当前阶段最终命中的命令。"""


class WorkflowExecutionMetric(BaseModel):
    """记录工作流执行阶段的命令运行情况。"""

    executed_commands: list[str] = Field(default_factory=list)
    """按实际执行顺序记录的命令序列。"""
    repeated_invocation: bool = False
    """是否出现重复调用同一条命令。"""
    repeated_commands: list[str] = Field(default_factory=list)
    """出现重复调用的命令名称列表。"""


class AgentObservabilityMetrics(BaseModel):
    """汇总一轮 AutoGPT 处理的关键可观测指标。"""

    trace_id: str = ""
    """本轮处理链路对应的 trace_id。"""
    prompt_stages: list[PromptStageMetric] = Field(default_factory=list)
    """各 Prompt 阶段的输入规模与召回情况。"""
    planner_candidate_commands: list[str] = Field(default_factory=list)
    """Planner 产出的候选命令列表。"""
    final_hit_commands: list[str] = Field(default_factory=list)
    """经过校验后真正保留下来的命令列表。"""
    execution: WorkflowExecutionMetric = Field(default_factory=WorkflowExecutionMetric)
    """工作流执行阶段的命令调用指标。"""
    runtime_roles: list[dict[str, Any]] = Field(default_factory=list)
    """Host 规划出的运行时角色轨迹摘要。"""


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
    """AutoGPT 工具投递后的结构化观察记录。

    历史名称保留为 ``CommandObservation``，但新代码按通用
    ToolObservation 语义写入 MCP、RAG、command 等结果。
    """

    trace_id: str = ""
    """本轮 AutoGPT 请求的追踪 ID。"""
    command: str
    """被投递的项目命令名称。"""
    source_type: ToolObservationSource = "command"
    """观察来源类型，例如 command、mcp_tool 或 external_rag。"""
    tool_name: str = ""
    """真实工具名称；未设置时等同于 command。"""
    user_goal: str = ""
    """当前工具调用服务的用户目标。"""
    query: str = ""
    """检索或查询类工具使用的查询文本。"""
    params: list[Param] = Field(default_factory=list)
    """本次随命令一起投递的参数。"""
    dispatch_type: Literal["command", "mcp_tool", "missing_command", "unsupported_command"] = "command"
    """投递类型：service 命令、缺失命令或尚未 service 化的命令。"""
    status: ToolObservationStatus = "succeeded"
    """工具调用状态，供最终回复判断能否可信回答。"""
    success: bool = True
    """是否成功通过统一命令执行器完成。"""
    relevance: ToolObservationRelevance = "unknown"
    """工具结果与用户目标的相关性。"""
    answer_quality: ToolObservationAnswerQuality = "unknown"
    """工具结果是否足够回答用户问题。"""
    message: str = ""
    """投递结果说明。"""
    display_summary: str = ""
    """面向最终回复器和兜底回复的安全摘要，不直接倾倒 raw output。"""
    context_summary: str = ""
    """写回上下文的短摘要，便于后续追问复用。"""
    outputs: list[str] = Field(default_factory=list)
    """命令执行产生的用户可见消息文本。"""
    context_outputs: list[str] = Field(default_factory=list)
    """写入 Agent 上下文的紧凑结果，未提供时回退到 outputs。"""
    raw_result: Any = None
    """完整原始结果，仅用于审计和调试，默认不面向普通用户。"""
    next_actions: list[str] = Field(default_factory=list)
    """质量门建议的下一步，例如 retry_search、ask_user 或 answer。"""
    outputs_sent_to_user: bool = True
    """outputs 是否已经由入口层发送给用户；service 命令通常为 ``False``。"""
    created_at: datetime = Field(default_factory=datetime.now)
    """观察记录创建时间。"""


ToolObservation = CommandObservation


class ReplyRecord(BaseModel):
    """记录用户真实看到的最终回复，供后续追问承接。"""

    trace_id: str = ""
    """本轮 AutoGPT 请求追踪 ID。"""
    reply: str = ""
    """最终发送给用户的自然语言回复。"""
    summary: str = ""
    """用于后续模型快速引用的短摘要。"""
    source_observations: list[str] = Field(default_factory=list)
    """本回复引用过的 observation 工具名称。"""
    language: str = "zh-CN"
    """最终回复语言。"""
    created_at: datetime = Field(default_factory=datetime.now)
    """记录创建时间。"""


class WorkflowStep(BaseModel):
    """描述一条可被执行器顺序运行的任务流步骤。"""

    step_id: str
    """步骤唯一标识。"""
    step_type: TaskWorkflowStepType = "command"
    """步骤类型；第一版主要执行 command，其余类型作为 AI 任务流扩展协议。"""
    title: str
    """面向日志和文档的步骤标题。"""
    command: str
    """步骤最终会调用的项目命令或 MCP tool 名称。"""
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


class TaskWorkflow(BaseModel):
    """描述 AI 为当前用户目标生成的任务执行流。"""

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
    observability: AgentObservabilityMetrics = Field(default_factory=AgentObservabilityMetrics)
    """当前工作流携带的结构化可观测指标。"""
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
    workflow: TaskWorkflow | None = None
    """面向执行层的 AI 任务执行流。"""
    observability: AgentObservabilityMetrics = Field(default_factory=AgentObservabilityMetrics)
    """本轮处理的结构化可观测指标。"""


class WorkflowExecutionResult(BaseModel):
    """描述任务执行流运行后的状态、观察记录与最终回复。"""

    workflow: TaskWorkflow
    """执行后的任务流对象。"""
    observations: list[CommandObservation] = Field(default_factory=list)
    """顺序执行过程中产生的观察记录。"""
    raw_outputs: list[str] = Field(default_factory=list)
    """命令产生且尚未直接发送给用户的原始可见输出。"""
    user_message: str | None = None
    """展示层可选的简短执行消息；最终回复优先使用 final_reply。"""
    final_reply: str | None = None
    """基于观察结果生成的最终自然语言回复。"""
    show_raw_outputs: bool = False
    """是否建议在最终回复后附带原始输出。"""
    observability: AgentObservabilityMetrics | None = None
    """工作流执行后的可观测指标快照。"""


@dataclass(slots=True)
class ChatMessage:
    "用户的聊天消息"

    role: Literal["user", "help"] = "user"
    "消息角色, user: 用户, help: 帮助文档"
    user_id: int | None = None
    "用户ID"
    message: list[Content] = field(default_factory=list)
    "消息内容"
    create_at: datetime = field(default_factory=datetime.now)
    "消息创建时间"

    def extend(self, message: UniMessage | str):
        """扩展当前集合。

        参数:
            message (UniMessage | str): 消息对象。
        """
        self.message.extend(uni_message_to_contents(message))
        return self.message
