from __future__ import annotations

import json
from collections import Counter
from typing import Any

from nonebot import get_driver
from nonebot_plugin_orm import get_session
from sqlalchemy import select

from src.core.skills import skill_registry
from src.core.agent.runtime.node_registry import RUNTIME_NODE_REGISTRY, list_runtime_node_definitions
from src.core.agent.runtime.orchestration_config import (
    AGENT_ORCHESTRATION_CONFIG_PATH,
    RuntimeGraphConfig,
    build_graph_config_from_designer,
    default_graph_designer_payload,
    is_designer_applied_to_runtime,
    normalize_runtime_edge_condition,
    normalize_runtime_edge_scene,
    reload_runtime_orchestration_config,
    stable_designer_hash,
    write_runtime_orchestration_config,
)
from src.core.agent.runtime.playbooks import playbook_catalog
from src.core.llm.config import plugin_config as llm_config
from src.platform.config import autogpt_dir, project_root, prompts_dir, skill_runtime_dir, skills_dir, storage_dir
from src.models import AgentWorkflowCheckpoint, AgentWorkflowRun
from ..runtime import nonebot
from ..service import manager_config_path, now_iso, relative_to_project
from .models import (
    AgentCheckpointSummaryPayload,
    AgentConfigItem,
    AgentControlItem,
    AgentDesignerApplyResult,
    AgentDesignerCapabilities,
    AgentDesignerDraft,
    AgentDesignerEdge,
    AgentDesignerLimits,
    AgentDesignerNode,
    AgentDesignerPayload,
    AgentDesignerRuntimeStatus,
    AgentDesignerSaveResult,
    AgentModuleCard,
    AgentModuleDefinition,
    AgentNodeConfigField,
    AgentNodeDraftConfig,
    AgentOrchestrationEdge,
    AgentOrchestrationNode,
    AgentOverviewMetrics,
    AgentOverviewOrchestration,
    AgentOverviewPayload,
    AgentOverviewStats,
    AgentOverviewDesignerSummary,
    AgentPlaybookItem,
    AgentPlaybookStep,
    AgentRunSummaryPayload,
    AgentSelectOption,
    AgentSkillItem,
    RuntimeNodePaletteItem,
)

driver: Any | None = None
DESIGNER_SCHEMA_VERSION = 1
DESIGNER_CONFIG_PATH = manager_config_path("agent_designer.json")
DESIGNER_MAX_NODES = 64
DESIGNER_MAX_EDGES = 128

AGENT_MODULES: tuple[AgentModuleDefinition, ...] = (
    AgentModuleDefinition(
        id="autogpt_entry",
        name="AutoGPT 消息入口",
        category="入口层",
        source="src/plugins/application/active/autogpt/__init__.py",
        description="接收 NoneBot 消息事件，组织会话、发送阶段反馈，并把可执行工作流交给执行器。",
        capabilities=("消息触发", "待确认恢复", "阶段反馈", "命令投递"),
        control_note="随 NoneBot 插件加载，当前没有独立启停接口。",
    ),
    AgentModuleDefinition(
        id="harness_runtime",
        name="AutoGPTHarness",
        category="运行时装配",
        source="src/core/agent/runtime/harness/runtime.py",
        description="把策略、上下文和可观测性三层依赖组装成一次 Agent 会话的统一入口。",
        capabilities=("依赖装配", "上下文注入", "可观测性接线"),
        control_note="运行时容器由会话创建，当前不提供后台修改。",
    ),
    AgentModuleDefinition(
        id="policy_harness",
        name="PolicyHarness",
        category="策略层",
        source="src/core/agent/runtime/harness/policy.py",
        description="收敛当前用户可见命令、结构化命令工具目录和 Skill 摘要。",
        capabilities=("命令裁剪", "候选命令解析", "Skill 召回"),
        control_note="命令软关闭由 Plugin 管理维护，Agent 会自动过滤不可用命令。",
    ),
    AgentModuleDefinition(
        id="context_harness",
        name="ContextHarness",
        category="上下文层",
        source="src/core/agent/runtime/harness/context.py",
        description="管理会话消息、运行时上下文、本地聊天记录和文件空间检索入口。",
        capabilities=("历史序列化", "本地上下文判断", "聊天记录接入"),
        control_note="上下文跟随当前消息和用户空间生成，当前不提供静态配置。",
    ),
    AgentModuleDefinition(
        id="observability_harness",
        name="ProgressFeedbackHarness",
        category="可观测性",
        source="src/core/agent/runtime/harness/observability.py",
        description="记录 Prompt 阶段指标、命令召回结果和重复调用等运行数据。",
        capabilities=("阶段指标", "进度反馈", "重复调用检测"),
        control_note="指标自动写入工作流快照，当前不提供关闭开关。",
    ),
    AgentModuleDefinition(
        id="pipeline",
        name="MessageProcessingPipeline",
        category="编排核心",
        source="src/core/agent/runtime/pipeline.py",
        description="按默认安全节点链完成本地查询、意图路由、上下文抽取、计划、RAG、任务生成和校验。",
        capabilities=("意图路由", "本地 RAG", "计划生成", "任务校验", "Runtime 图热更新"),
        control_note="节点编排可通过 Agent 设计器写入运行时配置；安全关键节点仍由后端校验保护。",
    ),
    AgentModuleDefinition(
        id="workflow",
        name="WorkflowBuilder / WorkflowExecutor",
        category="工作流",
        source="src/core/agent/runtime/workflow.py",
        description="把规划结果转换成显式工作流，并按步骤复用 NoneBot 命令系统执行。",
        capabilities=("显式工作流", "审批语义", "顺序执行", "执行观测"),
        control_note="工作流执行边界来自命令系统，当前不提供模块级启停。",
    ),
    AgentModuleDefinition(
        id="command_tools",
        name="CommandToolCatalog",
        category="命令工具",
        source="src/core/agent/runtime/command_tools.py",
        description="把 Helper 和统一命令注册表转换为 Agent 可规划的结构化命令工具。",
        capabilities=("命令元数据", "参数 Schema", "风险等级", "Agent 可调用过滤"),
        control_note="单条命令或插件可在 Plugin 管理中软关闭。",
    ),
    AgentModuleDefinition(
        id="local_knowledge",
        name="LocalKnowledgeRetriever",
        category="本地知识",
        source="src/core/agent/runtime/knowledge.py",
        description="按需检索用户聊天、群聊采集消息和隔离文件空间，并通过本地 RAG 汇总上下文。",
        capabilities=("聊天记录检索", "文件空间检索", "本地 RAG"),
        control_note="检索触发由用户问题和运行时上下文决定，当前不提供后台开关。",
    ),
    AgentModuleDefinition(
        id="skill_registry",
        name="SkillRegistry",
        category="Skill 能力",
        source="src/core/skills/registry.py",
        description="发现并加载项目内置 Skill，向 Agent 暴露稳定能力摘要。",
        capabilities=("Skill 发现", "运行时加载", "摘要召回"),
        control_note="Skill 文件维护在 Skill 管理中进行，Agent 侧当前只读消费。",
    ),
    AgentModuleDefinition(
        id="checkpoint_store",
        name="WorkflowCheckpointStore",
        category="持久化",
        source="src/core/agent/runtime/persistence/checkpoints.py",
        description="保存每个用户最近一次工作流状态，用于待确认任务恢复。",
        capabilities=("待确认恢复", "工作流快照"),
        control_note="检查点数据可在 Agent 管理中查看和删除。",
    ),
    AgentModuleDefinition(
        id="run_store",
        name="WorkflowRunStore",
        category="持久化",
        source="src/core/agent/runtime/persistence/runs.py",
        description="保存每次 Agent 工作流运行历史，供审计、排障和后台查看。",
        capabilities=("运行历史", "Trace 审计", "失败排查"),
        control_note="运行历史当前只读展示。",
    ),
)

ORCHESTRATION_EDGES: tuple[tuple[str, str, str, str], ...] = tuple(
    (
        str(edge.get("source") or ""),
        str(edge.get("target") or ""),
        str(edge.get("label") or ""),
        str(edge.get("condition") or "always"),
    )
    for edge in default_graph_designer_payload()["edges"]
)


def _get_manager_driver() -> Any:
    """返回缓存的 NoneBot Driver，避免导入 Agent 管理服务时依赖初始化状态。"""

    global driver

    if driver is None:
        driver = get_driver()
    return driver


class AgentManagerService:
    """封装 Agent 管理后台的展示拼装、草稿校验和运行态查询能力。"""

    def build_model_options(self) -> list[AgentSelectOption]:
        """导出 Agent 参数设计器可选择的模型名称。"""

        return [
            AgentSelectOption(
                label=config.name,
                value=config.name,
                model=config.model,
                multi_modal=config.multi_modal,
            )
            for config in llm_config.llm_configs
        ]

    def build_node_config_schema(self) -> list[AgentNodeConfigField]:
        """返回管理端 Agent 节点配置字段。"""

        return [
            AgentNodeConfigField(
                key="model",
                label="模型",
                type="select",
                options=self.build_model_options(),
                placeholder="继承系统默认模型",
                description="直接指定当前节点使用的模型；为空时按模型角色回退。",
                runtime_supported=True,
            ),
            AgentNodeConfigField(
                key="model_profile",
                label="模型角色",
                type="select",
                options=[
                    AgentSelectOption(label="继承节点默认", value=""),
                    AgentSelectOption(label="编排监督模型", value="supervisor"),
                    AgentSelectOption(label="执行工作模型", value="worker"),
                    AgentSelectOption(label="视觉模型", value="vision"),
                    AgentSelectOption(label="压缩模型", value="summary"),
                ],
                placeholder="继承节点默认角色",
                description="选择 supervisor、worker、vision 或 summary 角色，由运行时模型配置解析到具体模型。",
                runtime_supported=True,
            ),
            AgentNodeConfigField(
                key="temperature",
                label="温度",
                type="number",
                min=0,
                max=2,
                step=0.1,
                placeholder="继承默认",
                description="写入节点配置，用于规划、检索、回复等节点的生成随机性控制。",
                runtime_supported=False,
            ),
            AgentNodeConfigField(
                key="max_iterations",
                label="最大迭代",
                type="number",
                min=1,
                max=20,
                step=1,
                placeholder="继承默认",
                description="写入节点配置，用于后续工具循环和多 Agent 协作的安全上限。",
                runtime_supported=False,
            ),
            AgentNodeConfigField(
                key="timeout_seconds",
                label="超时秒数",
                type="number",
                min=1,
                max=600,
                step=1,
                placeholder="继承默认",
                description="写入节点配置，用于节点级模型请求、工具调用或外部集成超时控制。",
                runtime_supported=False,
            ),
            AgentNodeConfigField(
                key="risk_policy",
                label="风险策略",
                type="select",
                options=[
                    AgentSelectOption(label="继承系统策略", value=""),
                    AgentSelectOption(label="低风险自动执行", value="auto_low"),
                    AgentSelectOption(label="写操作必须确认", value="confirm_write"),
                    AgentSelectOption(label="全部人工确认", value="confirm_all"),
                ],
                placeholder="继承系统策略",
                description="写入节点配置，用于节点级审批策略；当前仍由 ExecutionPolicyNode 和命令风险等级控制。",
                runtime_supported=False,
            ),
        ]

    def build_run_summary(self, run: AgentWorkflowRun) -> AgentRunSummaryPayload:
        """序列化一条 Agent 运行记录摘要。"""

        return AgentRunSummaryPayload(
            id=run.id,
            user_id=run.user_id,
            trace_id=run.trace_id,
            source_trace_id=run.source_trace_id,
            kind=run.kind,
            status=run.status,
            goal=run.goal,
            summary=run.summary,
            playbook_id=run.playbook_id,
            playbook_name=run.playbook_name,
            approval_type=run.approval_type,
            approval_status=run.approval_status,
            approval_reason=run.approval_reason,
            started_at=run.started_at.isoformat() if run.started_at else None,
            finished_at=run.finished_at.isoformat() if run.finished_at else None,
            created_at=run.created_at.isoformat() if run.created_at else None,
            updated_at=run.updated_at.isoformat() if run.updated_at else None,
        )

    def build_checkpoint_summary(self, checkpoint: AgentWorkflowCheckpoint) -> AgentCheckpointSummaryPayload:
        """序列化一条 Agent 检查点摘要。"""

        return AgentCheckpointSummaryPayload(
            id=checkpoint.id,
            user_id=checkpoint.user_id,
            trace_id=checkpoint.trace_id,
            kind=checkpoint.kind,
            status=checkpoint.status,
            goal=checkpoint.goal,
            summary=checkpoint.summary,
            playbook_id=checkpoint.playbook_id,
            playbook_name=checkpoint.playbook_name,
            created_at=checkpoint.created_at.isoformat() if checkpoint.created_at else None,
            updated_at=checkpoint.updated_at.isoformat() if checkpoint.updated_at else None,
        )

    def source_status(self, source: str) -> str:
        """根据源码路径判断模块当前是否可用。"""

        return "enabled" if (project_root / source).exists() else "missing"

    def build_module_card(self, definition: AgentModuleDefinition) -> AgentModuleCard:
        """把静态模块定义转换为前端可消费的模块卡片。"""

        return AgentModuleCard(
            id=definition.id,
            name=definition.name,
            category=definition.category,
            source=definition.source,
            description=definition.description,
            capabilities=list(definition.capabilities),
            control_note=definition.control_note,
            status=self.source_status(definition.source),
            toggleable=False,
            configurable=False,
            draft_configurable=True,
            mutable=False,
            control_supported=False,
            runtime_config_supported=False,
            runtime_orchestration_supported=False,
            config_schema=self.build_node_config_schema(),
        )

    def build_runtime_palette(self) -> list[RuntimeNodePaletteItem]:
        """导出设计器可拖拽的 Runtime 节点调色板。"""

        items: list[RuntimeNodePaletteItem] = []
        for definition in list_runtime_node_definitions():
            items.append(
                RuntimeNodePaletteItem(
                    id=definition.node_type,
                    node_type=definition.node_type,
                    module_id=definition.module_id,
                    name=definition.label,
                    category=definition.phase,
                    source=definition.source,
                    description=definition.description,
                    capabilities=["Runtime 节点", "热更新编排"],
                    control_note="保存并热更新后会写入运行时编排配置；安全关键节点不能禁用。",
                    status=self.source_status(definition.source),
                    toggleable=definition.allow_disable,
                    configurable=False,
                    draft_configurable=True,
                    mutable=not definition.required,
                    control_supported=definition.allow_disable,
                    runtime_config_supported=False,
                    runtime_orchestration_supported=True,
                    required=definition.required,
                    allow_disable=definition.allow_disable,
                    config_schema=self.build_node_config_schema(),
                )
            )
        return items

    def build_default_designer_state(self) -> AgentDesignerDraft:
        """生成默认 Runtime 编排图的可视化草稿镜像。"""

        nodes: list[AgentDesignerNode] = []
        for index, definition in enumerate(list_runtime_node_definitions()):
            row = index // 4
            col = index % 4
            nodes.append(
                AgentDesignerNode(
                    id=definition.node_type,
                    node_type=definition.node_type,
                    module_id=definition.module_id,
                    label=definition.label,
                    phase=definition.phase,
                    x=56 + col * 220,
                    y=56 + row * 144,
                    enabled=True,
                    config=AgentNodeDraftConfig(),
                    runtime_applied=False,
                )
            )
        edges = [
            AgentDesignerEdge(
                id=f"{source}__{target}",
                source=source,
                target=target,
                label=label,
                condition=condition,
                runtime_applied=False,
            )
            for source, target, label, condition in ORCHESTRATION_EDGES
        ]
        return AgentDesignerDraft(
            version=DESIGNER_SCHEMA_VERSION,
            updated_at=None,
            note="当前草稿来自 AutoGPT Runtime 默认安全编排；保存并热更新后会影响后续新会话轮次。",
            nodes=nodes,
            edges=edges,
        )

    def build_designer_capabilities(self) -> AgentDesignerCapabilities:
        """描述 Agent 设计器当前能力和后续可扩展边界。"""

        return AgentDesignerCapabilities(
            draft_orchestration_supported=True,
            drag_node_supported=True,
            edge_edit_supported=True,
            draft_config_supported=True,
            runtime_apply_supported=True,
            runtime_apply_status="hot_reload",
            message="当前默认使用可编排 Runtime 图；保存并热更新后会影响后续 Agent 轮次。",
        )

    def read_designer_state(self) -> AgentDesignerDraft:
        """读取已保存的 Agent 编排草稿。"""

        if not DESIGNER_CONFIG_PATH.exists():
            return self.build_default_designer_state()
        try:
            data = json.loads(DESIGNER_CONFIG_PATH.read_text(encoding="utf-8"))
            return AgentDesignerDraft.parse_obj(data)
        except (OSError, json.JSONDecodeError, ValueError):
            return self.build_default_designer_state()

    def build_runtime_status(self) -> AgentDesignerRuntimeStatus:
        """返回当前 AutoGPT Runtime 编排配置状态。"""

        snapshot = reload_runtime_orchestration_config()
        return AgentDesignerRuntimeStatus(
            mode=snapshot.config.mode,
            enabled=snapshot.graph_enabled,
            valid=snapshot.valid,
            errors=list(snapshot.errors),
            warnings=list(snapshot.config.warnings),
            config_path=str(AGENT_ORCHESTRATION_CONFIG_PATH),
            hot_reload_supported=True,
            applied_at=snapshot.config.applied_at,
            updated_at=snapshot.config.updated_at,
            active_node_count=len(snapshot.config.node_order),
            active_edge_count=len(snapshot.config.edges),
        )

    def mark_runtime_applied(self, draft: AgentDesignerDraft) -> AgentDesignerDraft:
        """根据当前运行时配置标记草稿节点和连线是否已应用。"""

        cloned = AgentDesignerDraft.parse_obj(draft.to_payload())
        applied = is_designer_applied_to_runtime(cloned.to_payload(compact=True))
        for node in cloned.nodes:
            node.runtime_applied = applied and bool(node.enabled)
        for edge in cloned.edges:
            edge.runtime_applied = applied
        return cloned

    def normalize_number(self, value: Any, default: int, *, minimum: int = 0, maximum: int = 5000) -> int:
        """把画布坐标值标准化为安全整数。"""

        if isinstance(value, bool):
            return default
        if isinstance(value, (int, float)):
            return min(max(int(value), minimum), maximum)
        return default

    def normalize_node_config(self, config: AgentNodeDraftConfig | dict[str, Any] | None) -> AgentNodeDraftConfig:
        """过滤节点参数配置中的不支持字段。"""

        if isinstance(config, AgentNodeDraftConfig):
            return AgentNodeDraftConfig.parse_obj(config.to_payload(compact=True))
        if isinstance(config, dict):
            return AgentNodeDraftConfig.parse_obj(config)
        return AgentNodeDraftConfig()

    def validate_designer_state(self, payload: AgentDesignerDraft | dict[str, Any]) -> AgentDesignerDraft:
        """校验并标准化管理端提交的编排草稿。"""

        state = payload if isinstance(payload, AgentDesignerDraft) else AgentDesignerDraft.parse_obj(payload)
        if len(state.nodes) > DESIGNER_MAX_NODES:
            raise ValueError(f"Designer nodes must not exceed {DESIGNER_MAX_NODES}")
        if len(state.edges) > DESIGNER_MAX_EDGES:
            raise ValueError(f"Designer edges must not exceed {DESIGNER_MAX_EDGES}")

        module_ids = {definition.id for definition in AGENT_MODULES}
        nodes: list[AgentDesignerNode] = []
        node_ids: set[str] = set()

        for index, raw_node in enumerate(state.nodes):
            node_id = raw_node.id.strip()
            node_type = raw_node.node_type.strip()
            if not node_type and node_id in RUNTIME_NODE_REGISTRY:
                node_type = node_id
            definition = RUNTIME_NODE_REGISTRY.get(node_type)
            module_id = (raw_node.module_id or (definition.module_id if definition else "")).strip()
            if not node_id:
                raise ValueError(f"Designer node #{index + 1} is missing id")
            if node_id in node_ids:
                raise ValueError(f"Designer node id `{node_id}` is duplicated")
            if definition is None:
                raise ValueError(f"Designer node `{node_id}` references unknown runtime node type `{node_type}`")
            if module_id not in module_ids:
                raise ValueError(f"Designer node `{node_id}` references unknown module `{module_id}`")
            node_ids.add(node_id)
            nodes.append(
                AgentDesignerNode(
                    id=node_id,
                    node_type=node_type,
                    module_id=module_id,
                    label=(raw_node.label or definition.label).strip()[:80],
                    phase=(raw_node.phase or definition.phase).strip()[:40],
                    x=self.normalize_number(raw_node.x, 80),
                    y=self.normalize_number(raw_node.y, 80),
                    enabled=bool(raw_node.enabled),
                    config=self.normalize_node_config(raw_node.config),
                    runtime_applied=False,
                )
            )

        edges: list[AgentDesignerEdge] = []
        edge_ids: set[str] = set()
        for index, raw_edge in enumerate(state.edges):
            source = raw_edge.source.strip()
            target = raw_edge.target.strip()
            if source not in node_ids or target not in node_ids:
                raise ValueError(f"Designer edge #{index + 1} references missing nodes")
            if source == target:
                raise ValueError("Designer edge cannot connect a node to itself")
            edge_id = (raw_edge.id or f"{source}__{target}").strip()
            if edge_id in edge_ids:
                raise ValueError(f"Designer edge id `{edge_id}` is duplicated")
            edge_ids.add(edge_id)
            edges.append(
                AgentDesignerEdge(
                    id=edge_id,
                    source=source,
                    target=target,
                    label=raw_edge.label.strip()[:80],
                    condition=normalize_runtime_edge_condition(raw_edge.condition),
                    scene=normalize_runtime_edge_scene(raw_edge.scene),
                    runtime_applied=False,
                )
            )

        return AgentDesignerDraft(
            version=DESIGNER_SCHEMA_VERSION,
            updated_at=now_iso(),
            note=state.note.strip()[:500],
            nodes=nodes,
            edges=edges,
        )

    def get_designer_payload(self) -> AgentDesignerPayload:
        """读取 Agent 可视化编排设计器数据。"""

        draft = self.mark_runtime_applied(self.read_designer_state())
        return AgentDesignerPayload(
            capabilities=self.build_designer_capabilities(),
            palette=self.build_runtime_palette(),
            config_schema=self.build_node_config_schema(),
            model_options=self.build_model_options(),
            draft=draft,
            limits=AgentDesignerLimits(max_nodes=DESIGNER_MAX_NODES, max_edges=DESIGNER_MAX_EDGES),
            runtime=self.build_runtime_status(),
            applied_to_runtime=is_designer_applied_to_runtime(draft.to_payload(compact=True)),
        )

    def save_designer_payload(
        self,
        payload: AgentDesignerDraft | dict[str, Any],
        *,
        apply_to_runtime: bool = False,
    ) -> AgentDesignerSaveResult:
        """保存 Agent 可视化编排草稿。"""

        state = self.validate_designer_state(payload)
        runtime_config = (
            build_graph_config_from_designer(state.to_payload(compact=True), applied_at=now_iso())
            if apply_to_runtime
            else None
        )
        DESIGNER_CONFIG_PATH.write_text(
            json.dumps(state.to_payload(compact=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if runtime_config is not None:
            self.apply_designer_state(state, runtime_config=runtime_config)
        designer = self.get_designer_payload()
        applied = bool(apply_to_runtime and designer.applied_to_runtime)
        return AgentDesignerSaveResult(
            saved=True,
            applied_to_runtime=applied,
            restart_required=False,
            designer=designer,
            message="已保存并热更新到 AutoGPT Runtime。" if applied else "已保存为管理端 Agent 编排草稿。",
        )

    def apply_designer_state(
        self,
        state: AgentDesignerDraft | dict[str, Any] | None = None,
        *,
        runtime_config: RuntimeGraphConfig | None = None,
    ) -> AgentDesignerApplyResult:
        """将当前设计器草稿写入运行时配置并热更新当前进程。"""

        draft = self.validate_designer_state(state or self.read_designer_state())
        compact_draft = draft.to_payload(compact=True)
        runtime_config_to_apply = runtime_config or build_graph_config_from_designer(compact_draft, applied_at=now_iso())
        write_runtime_orchestration_config(runtime_config_to_apply)
        snapshot = reload_runtime_orchestration_config(force=True)
        if not snapshot.valid or not snapshot.graph_enabled:
            raise ValueError("; ".join(snapshot.errors) or "Runtime graph config did not become active")
        return AgentDesignerApplyResult(
            applied=True,
            applied_to_runtime=is_designer_applied_to_runtime(compact_draft, snapshot),
            restart_required=False,
            source_hash=stable_designer_hash(compact_draft),
            runtime=self.build_runtime_status(),
            designer=self.get_designer_payload(),
            message="已写入运行时编排配置，并对后续 Agent 轮次热更新生效。",
        )

    def build_skill_items(self) -> list[AgentSkillItem]:
        """导出 Agent 当前可见的 Skill 摘要。"""

        loaded_classes = getattr(skill_registry, "_classes", {})
        return [
            AgentSkillItem(
                name=manifest.name,
                description=manifest.description,
                path=relative_to_project(manifest.root),
                loaded=manifest.name in loaded_classes,
                runtime=manifest.name in loaded_classes,
            )
            for manifest in sorted(skill_registry.manifests.values(), key=lambda item: item.name)
        ]

    def build_playbook_items(self) -> list[AgentPlaybookItem]:
        """导出内置工作流模板。"""

        return [
            AgentPlaybookItem(
                id=playbook.playbook_id,
                name=playbook.name,
                description=playbook.description,
                step_count=len(playbook.steps),
                steps=[
                    AgentPlaybookStep(
                        command=step.command,
                        title=step.title,
                        description=step.description,
                    )
                    for step in playbook.steps
                ],
            )
            for playbook in playbook_catalog.playbooks
        ]

    def build_config_items(
        self,
        agent_callable_commands: int,
        available_agent_commands: int,
        agent_executable_commands: int,
    ) -> list[AgentConfigItem]:
        """生成 Agent 相关配置快照。"""

        current_driver = _get_manager_driver()
        driver_config = current_driver.config
        prompt_names = [
            "intent_route.jinja",
            "extract.jinja",
            "agent_plan.jinja",
            "auto_task.jinja",
            "vision_reply.jinja",
        ]
        existing_prompts = [name for name in prompt_names if (prompts_dir / name).exists()]
        llm_configs = list(llm_config.llm_configs)
        multi_modal_models = [item for item in llm_configs if item.multi_modal]
        return [
            AgentConfigItem(
                id="nonebot_driver",
                group="运行时",
                name="NoneBot Driver",
                value=str(getattr(driver_config, "driver", "")) or current_driver.__class__.__name__,
                description="Agent 入口随当前 NoneBot Driver 运行。",
                source="driver.config",
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="environment",
                group="运行时",
                name="运行环境",
                value=str(getattr(driver_config, "environment", "") or "-"),
                description="来自当前进程的运行环境配置。",
                source="driver.config.environment",
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="llm_configs",
                group="模型",
                name="模型配置",
                value=f"{len(llm_configs)} 个模型，{len(multi_modal_models)} 个支持多模态",
                description="Agent 路由、规划、任务生成和视觉回复复用统一 LLM 配置。",
                source="src.core.llm.config.plugin_config",
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="llm_timeout",
                group="模型",
                name="模型超时",
                value=f"{llm_config.llm_timeout:g}s",
                description="单次模型请求超时时间。",
                source="src.core.llm.config.plugin_config.llm_timeout",
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="prompt_templates",
                group="Prompt",
                name="Agent Prompt",
                value=f"{len(existing_prompts)}/{len(prompt_names)} 个关键模板存在",
                description="包含意图路由、上下文抽取、显式计划、任务生成和视觉回复模板。",
                source=relative_to_project(prompts_dir),
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="runtime_orchestration_config",
                group="Runtime",
                name="Agent 工作流编排配置",
                value=relative_to_project(AGENT_ORCHESTRATION_CONFIG_PATH),
                description="管理端保存并热更新后的 Runtime 编排图，固定存放在 resources/agent 中。",
                source=relative_to_project(AGENT_ORCHESTRATION_CONFIG_PATH),
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="skill_root",
                group="Skill",
                name="Skill 资源目录",
                value=relative_to_project(skills_dir),
                description="Agent Skill 的 SKILL.md 资源由 SkillRegistry 从该目录发现。",
                source="src.platform.config.skills_dir",
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="skill_runtime_root",
                group="Skill",
                name="Skill 代码目录",
                value=relative_to_project(skill_runtime_dir),
                description="Skill 的 runtime.py 代码从该目录加载。",
                source="src.platform.config.skill_runtime_dir",
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="command_availability",
                group="命令边界",
                name="Agent 可调用命令",
                value=f"{agent_executable_commands} 个实际可执行，{available_agent_commands}/{agent_callable_commands} 个声明可用",
                description="Agent 工具目录只暴露已启用、声明可调用、service 化且已注册 handler 的命令。",
                source="src.platform.commands.availability",
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="local_rag",
                group="本地上下文",
                name="本地 RAG 与文件空间",
                value="已接入聊天记录与文件空间",
                description="按需读取用户空间、群组空间、聊天记录和本地 RAG 索引。",
                source=relative_to_project(storage_dir),
                editable=False,
                toggleable=False,
            ),
            AgentConfigItem(
                id="autogpt_store",
                group="持久化",
                name="AutoGPT 数据目录",
                value=relative_to_project(autogpt_dir),
                description="用于保存 Agent 相关运行态文件和后续扩展数据。",
                source="src.platform.config.autogpt_dir",
                editable=False,
                toggleable=False,
            ),
        ]

    def build_controls(self) -> list[AgentControlItem]:
        """描述当前 Agent 管理可提供的控制能力。"""

        return [
            AgentControlItem(
                id="agent_module_toggle",
                name="Agent 模块启停",
                supported=False,
                status="readonly",
                description="当前 AutoGPT 模块随 NoneBot 插件和源码编排运行，没有独立模块级启停状态。",
                route=None,
            ),
            AgentControlItem(
                id="agent_module_config",
                name="Agent 模块配置修改",
                supported=False,
                status="readonly",
                description="当前配置主要来自 driver.config、LLM 配置、Prompt、Skill 和命令注册表，Agent 模块本身未暴露单独配置写入接口。",
                route=None,
            ),
            AgentControlItem(
                id="command_soft_switch",
                name="命令与插件软关闭",
                supported=True,
                status="delegated",
                description="Plugin 管理已支持命令和插件软关闭；Agent 工具目录会自动过滤不可用命令。",
                route="/nonebot/plugins",
            ),
            AgentControlItem(
                id="agent_runtime_orchestration",
                name="Agent Runtime 编排热更新",
                supported=True,
                status="available",
                description="Agent 设计器可以把合法 DAG 写入运行时配置，后续新 Agent 轮次会自动读取。",
                route="/agents/designer",
            ),
            AgentControlItem(
                id="checkpoint_delete",
                name="检查点清理",
                supported=True,
                status="available",
                description="Agent 管理已支持删除指定用户的检查点，用于清理卡住的待确认流程。",
                route="/agents",
            ),
        ]

    async def get_overview_payload(self) -> AgentOverviewPayload:
        """读取 Agent 管理页的完整概览数据。"""

        runs = await AgentWorkflowRun.filter().all()
        checkpoints = await AgentWorkflowCheckpoint.filter().all()
        run_status_counts = Counter(run.status for run in runs)
        run_kind_counts = Counter(run.kind for run in runs)
        checkpoint_status_counts = Counter(checkpoint.status for checkpoint in checkpoints)
        commands = nonebot.list_commands()["items"]
        agent_commands = [command for command in commands if command.get("agent_callable")]
        available_agent_commands = [command for command in agent_commands if command.get("available", True)]
        agent_executable_commands = [command for command in commands if command.get("agent_executable")]
        modules = [self.build_module_card(definition) for definition in AGENT_MODULES]
        skills = self.build_skill_items()
        playbooks = self.build_playbook_items()
        designer_state = self.read_designer_state()
        capabilities = self.build_designer_capabilities()
        orchestration = AgentOverviewOrchestration(
            nodes=[
                AgentOrchestrationNode(
                    id=definition.node_type,
                    node_type=definition.node_type,
                    label=definition.label,
                    phase=definition.phase,
                    module_id=definition.module_id,
                    description=definition.description,
                    required=definition.required,
                    allow_disable=definition.allow_disable,
                    order=index + 1,
                    status="enabled",
                )
                for index, definition in enumerate(list_runtime_node_definitions())
            ],
            edges=[
                AgentOrchestrationEdge.parse_obj({"from": source, "to": target, "label": label})
                for source, target, label, _condition in ORCHESTRATION_EDGES
            ],
        )
        return AgentOverviewPayload(
            stats=AgentOverviewStats(
                modules=len(modules),
                enabled_modules=sum(1 for module in modules if module.status == "enabled"),
                skills=len(skills),
                loaded_skills=sum(1 for item in skills if item.loaded),
                playbooks=len(playbooks),
                agent_callable_commands=len(agent_commands),
                available_agent_commands=len(available_agent_commands),
                agent_executable_commands=len(agent_executable_commands),
                runs=len(runs),
                pending_checkpoints=checkpoint_status_counts.get("needs_confirm", 0),
                failed_runs=run_status_counts.get("failed", 0),
            ),
            modules=modules,
            designer=AgentOverviewDesignerSummary(
                draft_orchestration_supported=capabilities.draft_orchestration_supported,
                drag_node_supported=capabilities.drag_node_supported,
                edge_edit_supported=capabilities.edge_edit_supported,
                draft_config_supported=capabilities.draft_config_supported,
                runtime_apply_supported=capabilities.runtime_apply_supported,
                runtime_apply_status=capabilities.runtime_apply_status,
                message=capabilities.message,
                draft_nodes=len(designer_state.nodes),
                draft_edges=len(designer_state.edges),
                saved_at=designer_state.updated_at,
            ),
            orchestration=orchestration,
            config=self.build_config_items(
                len(agent_commands),
                len(available_agent_commands),
                len(agent_executable_commands),
            ),
            controls=self.build_controls(),
            playbooks=playbooks,
            skills=skills,
            metrics=AgentOverviewMetrics(
                runs_by_status=dict(sorted(run_status_counts.items())),
                runs_by_kind=dict(sorted(run_kind_counts.items())),
                checkpoints_by_status=dict(sorted(checkpoint_status_counts.items())),
            ),
        )

    async def list_runs(
        self,
        *,
        status: str | None = None,
        kind: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """按条件列出 Agent 运行记录。"""

        runs = await AgentWorkflowRun.filter().all()
        if status:
            runs = [run for run in runs if run.status == status]
        if kind:
            runs = [run for run in runs if run.kind == kind]
        if q:
            q_lower = q.lower()
            runs = [
                run
                for run in runs
                if q_lower in run.trace_id.lower()
                or q_lower in (run.goal or "").lower()
                or q_lower in (run.summary or "").lower()
            ]
        runs.sort(key=lambda item: item.id, reverse=True)
        total = len(runs)
        start = max(page - 1, 0) * page_size
        end = start + page_size
        return {
            "items": [self.build_run_summary(run).to_payload() for run in runs[start:end]],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    async def get_run(self, trace_id: str) -> dict[str, Any]:
        """读取单条 Agent 运行详情。"""

        run = await AgentWorkflowRun.filter(trace_id=trace_id).first()
        if run is None:
            raise KeyError(trace_id)
        payload = self.build_run_summary(run)
        payload.workflow_data = run.workflow_data
        return payload.to_payload()

    async def list_checkpoints(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """列出 Agent 工作流检查点。"""

        checkpoints = await AgentWorkflowCheckpoint.filter().all()
        if status:
            checkpoints = [checkpoint for checkpoint in checkpoints if checkpoint.status == status]
        checkpoints.sort(key=lambda item: item.id, reverse=True)
        total = len(checkpoints)
        start = max(page - 1, 0) * page_size
        end = start + page_size
        return {
            "items": [self.build_checkpoint_summary(checkpoint).to_payload() for checkpoint in checkpoints[start:end]],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    async def get_checkpoint(self, user_id: int) -> dict[str, Any]:
        """读取指定用户的检查点详情。"""

        checkpoint = await AgentWorkflowCheckpoint.filter(user_id=user_id).first()
        if checkpoint is None:
            raise KeyError(str(user_id))
        payload = self.build_checkpoint_summary(checkpoint)
        payload.workflow_data = checkpoint.workflow_data
        return payload.to_payload()

    async def delete_checkpoint(self, user_id: int) -> dict[str, Any]:
        """删除指定用户的检查点。"""

        async with get_session() as session:
            checkpoint = await session.scalar(
                select(AgentWorkflowCheckpoint).where(AgentWorkflowCheckpoint.user_id == user_id)
            )
            if checkpoint is None:
                raise KeyError(str(user_id))
            await session.delete(checkpoint)
            await session.commit()
        return {"deleted": True, "user_id": user_id}


agent_manager_service = AgentManagerService()


def get_designer() -> dict[str, Any]:
    """读取 Agent 可视化编排设计器数据。"""

    return agent_manager_service.get_designer_payload().to_payload()


def save_designer(payload: AgentDesignerDraft | dict[str, Any], *, apply_to_runtime: bool = False) -> dict[str, Any]:
    """保存 Agent 可视化编排草稿。"""

    return agent_manager_service.save_designer_payload(payload, apply_to_runtime=apply_to_runtime).to_payload()


def apply_designer_state(
    state: AgentDesignerDraft | dict[str, Any] | None = None,
    *,
    runtime_config: Any | None = None,
) -> dict[str, Any]:
    """将当前设计器草稿写入运行时配置并热更新当前进程。"""

    return agent_manager_service.apply_designer_state(state, runtime_config=runtime_config).to_payload()


async def get_overview() -> dict[str, Any]:
    """读取 Agent 管理页的完整概览数据。"""

    return (await agent_manager_service.get_overview_payload()).to_payload()


async def list_runs(
    *,
    status: str | None = None,
    kind: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """按条件列出 Agent 运行记录。"""

    return await agent_manager_service.list_runs(status=status, kind=kind, q=q, page=page, page_size=page_size)


async def get_run(trace_id: str) -> dict[str, Any]:
    """读取单条 Agent 运行详情。"""

    return await agent_manager_service.get_run(trace_id)


async def list_checkpoints(
    *,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """列出 Agent 工作流检查点。"""

    return await agent_manager_service.list_checkpoints(status=status, page=page, page_size=page_size)


async def get_checkpoint(user_id: int) -> dict[str, Any]:
    """读取指定用户的检查点详情。"""

    return await agent_manager_service.get_checkpoint(user_id)


async def delete_checkpoint(user_id: int) -> dict[str, Any]:
    """删除指定用户的检查点。"""

    return await agent_manager_service.delete_checkpoint(user_id)
