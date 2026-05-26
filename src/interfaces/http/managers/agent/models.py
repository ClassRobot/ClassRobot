from __future__ import annotations

from typing import Any, Literal
from dataclasses import dataclass

from pydantic import Field, BaseModel, validator, root_validator


class AgentPayloadModel(BaseModel):
    """Agent 管理模块的统一数据模型基类。"""

    class Config:
        """统一允许忽略额外字段，并支持字段名回填。"""

        extra = "ignore"
        allow_population_by_field_name = True

    def to_payload(self, *, compact: bool = False) -> dict[str, Any]:
        """导出适合接口响应或持久化的字典数据。

        Args:
            compact: 为 ``True`` 时省略值为 ``None`` 的字段，便于写入配置文件。

        Returns:
            dict[str, Any]: 序列化后的字典结果。
        """

        return self.dict(exclude_none=compact, by_alias=True)


@dataclass(frozen=True, slots=True)
class AgentModuleDefinition:
    """描述一个可在管理后台展示的 Agent 模块。"""

    id: str
    name: str
    category: str
    source: str
    description: str
    capabilities: tuple[str, ...]
    control_note: str


class AgentSelectOption(AgentPayloadModel):
    """通用下拉选项定义。"""

    label: str
    value: str
    model: str | None = None
    multi_modal: bool | None = None


class AgentNodeConfigField(AgentPayloadModel):
    """Agent 节点配置表单字段定义。"""

    key: str
    label: str
    type: Literal["select", "number"]
    options: list[AgentSelectOption] = Field(default_factory=list)
    placeholder: str = ""
    description: str = ""
    runtime_supported: bool = False
    min: float | int | None = None
    max: float | int | None = None
    step: float | int | None = None


class AgentNodeDraftConfig(AgentPayloadModel):
    """Agent 设计器节点的扩展配置。"""

    model: str | None = None
    model_profile: str | None = None
    temperature: float | None = None
    max_iterations: int | None = None
    timeout_seconds: int | None = None
    risk_policy: str | None = None

    @root_validator(pre=True)
    def normalize_empty_values(cls, values: Any) -> dict[str, Any]:
        """把空字符串归一化为 ``None``，避免数值字段解析报错。"""

        if not isinstance(values, dict):
            return {}
        normalized = dict(values)
        for key, value in tuple(normalized.items()):
            if value == "":
                normalized[key] = None
        return normalized

    @validator("temperature")
    def validate_temperature(cls, value: float | None) -> float | None:
        """限制温度范围，避免写入明显错误的配置。"""

        if value is not None and not 0 <= value <= 2:
            raise ValueError("temperature must be between 0 and 2")
        return value

    @validator("max_iterations")
    def validate_max_iterations(cls, value: int | None) -> int | None:
        """限制最大迭代次数范围。"""

        if value is not None and not 1 <= value <= 20:
            raise ValueError("max_iterations must be between 1 and 20")
        return value

    @validator("timeout_seconds")
    def validate_timeout_seconds(cls, value: int | None) -> int | None:
        """限制节点超时范围。"""

        if value is not None and not 1 <= value <= 600:
            raise ValueError("timeout_seconds must be between 1 and 600")
        return value


class AgentDesignerNode(AgentPayloadModel):
    """Agent 设计器中的一个节点。"""

    id: str = ""
    node_type: str = ""
    module_id: str = ""
    label: str = ""
    phase: str = ""
    x: int = 80
    y: int = 80
    enabled: bool = True
    config: AgentNodeDraftConfig = Field(default_factory=AgentNodeDraftConfig)
    runtime_applied: bool = False

    def to_payload(self, *, compact: bool = False) -> dict[str, Any]:
        """导出节点数据，并始终压缩配置字段。"""

        payload = super().to_payload(compact=compact)
        payload["config"] = self.config.to_payload(compact=True)
        return payload


class AgentDesignerEdge(AgentPayloadModel):
    """Agent 设计器中的一条有向边。"""

    id: str = ""
    source: str = ""
    target: str = ""
    label: str = ""
    condition: str = "always"
    scene: str | None = None
    runtime_applied: bool = False


class AgentDesignerDraft(AgentPayloadModel):
    """Agent 设计器草稿。"""

    version: int = 1
    updated_at: str | None = None
    note: str = ""
    nodes: list[AgentDesignerNode] = Field(default_factory=list)
    edges: list[AgentDesignerEdge] = Field(default_factory=list)

    def to_payload(self, *, compact: bool = False) -> dict[str, Any]:
        """导出草稿数据，并递归压缩节点与连线。"""

        payload = super().to_payload(compact=compact)
        payload["nodes"] = [node.to_payload(compact=compact) for node in self.nodes]
        payload["edges"] = [edge.to_payload(compact=compact) for edge in self.edges]
        return payload


class AgentDesignerCapabilities(AgentPayloadModel):
    """描述 Agent 设计器能力边界。"""

    draft_orchestration_supported: bool
    drag_node_supported: bool
    edge_edit_supported: bool
    draft_config_supported: bool
    runtime_apply_supported: bool
    runtime_apply_status: str
    message: str


class AgentDesignerRuntimeStatus(AgentPayloadModel):
    """运行时编排状态快照。"""

    mode: str
    enabled: bool
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    config_path: str
    hot_reload_supported: bool
    applied_at: str | None = None
    updated_at: str | None = None
    active_node_count: int
    active_edge_count: int


class AgentDesignerLimits(AgentPayloadModel):
    """Agent 设计器容量限制。"""

    max_nodes: int
    max_edges: int


class AgentModuleCard(AgentPayloadModel):
    """Agent 模块展示卡片。"""

    id: str
    name: str
    category: str
    source: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    control_note: str
    status: str
    toggleable: bool
    configurable: bool
    draft_configurable: bool
    mutable: bool
    control_supported: bool
    runtime_config_supported: bool
    runtime_orchestration_supported: bool
    config_schema: list[AgentNodeConfigField] = Field(default_factory=list)


class RuntimeNodePaletteItem(AgentModuleCard):
    """运行时节点调色板项。"""

    node_type: str
    module_id: str = ""
    required: bool = False
    allow_disable: bool = True


class AgentDesignerPayload(AgentPayloadModel):
    """Agent 设计器详情接口载荷。"""

    capabilities: AgentDesignerCapabilities
    palette: list[RuntimeNodePaletteItem] = Field(default_factory=list)
    config_schema: list[AgentNodeConfigField] = Field(default_factory=list)
    model_options: list[AgentSelectOption] = Field(default_factory=list)
    draft: AgentDesignerDraft
    limits: AgentDesignerLimits
    runtime: AgentDesignerRuntimeStatus
    applied_to_runtime: bool

    def to_payload(self, *, compact: bool = False) -> dict[str, Any]:
        """导出设计器详情，并保留草稿的压缩配置结构。"""

        payload = super().to_payload(compact=compact)
        payload["capabilities"] = self.capabilities.to_payload(compact=compact)
        payload["palette"] = [item.to_payload(compact=compact) for item in self.palette]
        payload["config_schema"] = [item.to_payload(compact=compact) for item in self.config_schema]
        payload["model_options"] = [item.to_payload(compact=compact) for item in self.model_options]
        payload["draft"] = self.draft.to_payload(compact=compact)
        payload["limits"] = self.limits.to_payload(compact=compact)
        payload["runtime"] = self.runtime.to_payload(compact=compact)
        return payload


class AgentDesignerSaveResult(AgentPayloadModel):
    """保存 Agent 草稿后的返回结果。"""

    saved: bool
    applied_to_runtime: bool
    restart_required: bool
    designer: AgentDesignerPayload
    message: str

    def to_payload(self, *, compact: bool = False) -> dict[str, Any]:
        """导出保存结果，并递归序列化设计器详情。"""

        payload = super().to_payload(compact=compact)
        payload["designer"] = self.designer.to_payload(compact=compact)
        return payload


class AgentDesignerApplyResult(AgentPayloadModel):
    """将草稿应用到运行时后的返回结果。"""

    applied: bool
    applied_to_runtime: bool
    restart_required: bool
    source_hash: str
    runtime: AgentDesignerRuntimeStatus
    designer: AgentDesignerPayload
    message: str

    def to_payload(self, *, compact: bool = False) -> dict[str, Any]:
        """导出热更新结果，并递归序列化运行时和设计器详情。"""

        payload = super().to_payload(compact=compact)
        payload["runtime"] = self.runtime.to_payload(compact=compact)
        payload["designer"] = self.designer.to_payload(compact=compact)
        return payload


class AgentSkillItem(AgentPayloadModel):
    """Agent 可见 Skill 摘要。"""

    name: str
    description: str
    path: str
    loaded: bool
    runtime: bool


class AgentPlaybookStep(AgentPayloadModel):
    """Playbook 中的一步命令摘要。"""

    command: str
    title: str
    description: str


class AgentPlaybookItem(AgentPayloadModel):
    """Playbook 展示项。"""

    id: str
    name: str
    description: str
    step_count: int
    steps: list[AgentPlaybookStep] = Field(default_factory=list)


class AgentConfigItem(AgentPayloadModel):
    """Agent 配置快照展示项。"""

    id: str
    group: str
    name: str
    value: str
    description: str
    source: str
    editable: bool
    toggleable: bool


class AgentControlItem(AgentPayloadModel):
    """Agent 控制能力展示项。"""

    id: str
    name: str
    supported: bool
    status: str
    description: str
    route: str | None = None


class AgentOverviewStats(AgentPayloadModel):
    """Agent 管理首页统计数据。"""

    modules: int
    enabled_modules: int
    skills: int
    loaded_skills: int
    playbooks: int
    agent_callable_commands: int
    available_agent_commands: int
    agent_executable_commands: int
    runs: int
    pending_checkpoints: int
    failed_runs: int


class AgentOverviewDesignerSummary(AgentPayloadModel):
    """Agent 首页中的设计器摘要。"""

    draft_orchestration_supported: bool
    drag_node_supported: bool
    edge_edit_supported: bool
    draft_config_supported: bool
    runtime_apply_supported: bool
    runtime_apply_status: str
    message: str
    draft_nodes: int
    draft_edges: int
    saved_at: str | None = None


class AgentOrchestrationNode(AgentPayloadModel):
    """概览页中展示的一条编排节点定义。"""

    id: str
    node_type: str
    label: str
    phase: str
    module_id: str
    description: str
    required: bool
    allow_disable: bool
    order: int
    status: str


class AgentOrchestrationEdge(AgentPayloadModel):
    """概览页中的一条编排连线。"""

    from_: str = Field(alias="from")
    to: str
    label: str


class AgentOverviewOrchestration(AgentPayloadModel):
    """概览页中的默认编排结构。"""

    nodes: list[AgentOrchestrationNode] = Field(default_factory=list)
    edges: list[AgentOrchestrationEdge] = Field(default_factory=list)


class AgentOverviewMetrics(AgentPayloadModel):
    """Agent 运行统计分布。"""

    runs_by_status: dict[str, int] = Field(default_factory=dict)
    runs_by_kind: dict[str, int] = Field(default_factory=dict)
    checkpoints_by_status: dict[str, int] = Field(default_factory=dict)


class AgentOverviewPayload(AgentPayloadModel):
    """Agent 管理概览页接口载荷。"""

    stats: AgentOverviewStats
    modules: list[AgentModuleCard] = Field(default_factory=list)
    designer: AgentOverviewDesignerSummary
    orchestration: AgentOverviewOrchestration
    config: list[AgentConfigItem] = Field(default_factory=list)
    controls: list[AgentControlItem] = Field(default_factory=list)
    playbooks: list[AgentPlaybookItem] = Field(default_factory=list)
    skills: list[AgentSkillItem] = Field(default_factory=list)
    metrics: AgentOverviewMetrics


class AgentRunSummaryPayload(AgentPayloadModel):
    """Agent 运行记录摘要。"""

    id: int
    user_id: int
    trace_id: str
    source_trace_id: str | None = None
    kind: str
    status: str
    goal: str
    summary: str
    playbook_id: str | None = None
    playbook_name: str | None = None
    approval_type: str | None = None
    approval_status: str | None = None
    approval_reason: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    workflow_data: dict[str, Any] | None = None


class AgentCheckpointSummaryPayload(AgentPayloadModel):
    """Agent 检查点摘要。"""

    id: int
    user_id: int
    trace_id: str
    kind: str
    status: str
    goal: str
    summary: str
    playbook_id: str | None = None
    playbook_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    workflow_data: dict[str, Any] | None = None


class AgentLiveTraceEventPayload(AgentPayloadModel):
    """Agent 开发态实时事件。"""

    sequence: int
    trace_id: str
    user_id: int | None = None
    session_id: str = ""
    message_preview: str = ""
    event_type: str
    stage: str = ""
    node_type: str = ""
    node_label: str = ""
    status: str = ""
    workflow_kind: str = ""
    step_id: str = ""
    tool_name: str = ""
    model_name: str = ""
    params_preview: Any = None
    observation_summary: str = ""
    error: str = ""
    duration_ms: float | None = None
    created_at: str


class AgentLiveTraceSummaryPayload(AgentPayloadModel):
    """Agent live trace 列表摘要。"""

    trace_id: str
    user_id: int | None = None
    session_id: str = ""
    message_preview: str = ""
    status: str
    current_stage: str
    current_node: str = ""
    workflow_kind: str = ""
    current_tool: str = ""
    event_count: int
    started_at: str
    updated_at: str
    finished_at: str | None = None


class AgentLiveTraceDetailPayload(AgentLiveTraceSummaryPayload):
    """Agent live trace 详情。"""

    events: list[AgentLiveTraceEventPayload] = Field(default_factory=list)
    history_run: dict[str, Any] | None = None


class AgentLiveTraceStatusPayload(AgentPayloadModel):
    """Agent live trace 注册表状态。"""

    enabled: bool
    max_traces: int
    max_events_per_trace: int
    retention_seconds: int
    include_debug_preview: bool
    active_count: int
    trace_count: int
