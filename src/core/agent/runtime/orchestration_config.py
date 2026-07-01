from __future__ import annotations

import json
from pathlib import Path
from hashlib import sha256
from typing import Any, Literal
from dataclasses import dataclass

from nonebot import logger
from src.platform.config import agent_resources_dir
from pydantic import Field, BaseModel, field_validator

from .schema import RuntimeScene
from .node_registry import (
    RUNTIME_NODE_REGISTRY,
    DEFAULT_RUNTIME_NODE_ORDER,
    REQUIRED_RUNTIME_NODE_TYPES,
    list_runtime_node_definitions,
)

AGENT_ORCHESTRATION_CONFIG_PATH = agent_resources_dir / "agent_orchestration_runtime.json"
GRAPH_CONFIG_VERSION = 1
RuntimeEdgeCondition = Literal[
    "always",
    "has_auto_tasks",
    "no_auto_tasks",
    "needs_local_knowledge",
    "needs_external_rag",
    "direct_vision_reply",
    "scene_chat",
    "scene_command",
    "scene_knowledge",
    "scene_vision",
    "scene_task",
    "scene_violation",
]


class ModelProfileConfig(BaseModel):
    """描述开发者为运行时不同模型角色绑定的模型名称。"""

    supervisor_model: str | None = None
    """负责任务规划、风险监督和最终回复的模型。"""
    worker_model: str | None = None
    """负责抽取、检索摘要等中间工作的模型。"""
    vision_model: str | None = None
    """负责图片或文件理解的多模态模型。"""
    summary_model: str | None = None
    """负责长上下文压缩的模型。"""

    def get_model_for_role(self, role: str | None) -> str | None:
        """按模型角色返回配置的模型名。"""

        if role == "supervisor":
            return self.supervisor_model
        if role == "worker":
            return self.worker_model
        if role == "vision":
            return self.vision_model
        if role == "summary":
            return self.summary_model
        return None


class RuntimeGraphEdge(BaseModel):
    """描述运行时编排图中的一条有向边。"""

    id: str
    source: str
    target: str
    label: str = ""
    condition: RuntimeEdgeCondition = "always"
    scene: RuntimeScene | None = None
    runtime_applied: bool = True


class RuntimeNodeConfig(BaseModel):
    """描述运行时编排图中的一个节点配置。"""

    id: str
    node_type: str
    module_id: str = ""
    label: str = ""
    phase: str = ""
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    runtime_applied: bool = True

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, value: str) -> str:
        if value not in RUNTIME_NODE_REGISTRY:
            raise ValueError(f"unknown runtime node type `{value}`")
        return value


class RuntimeGraphConfig(BaseModel):
    """持久化到 resources/agent 的 AutoGPT Runtime 编排配置。"""

    version: int = GRAPH_CONFIG_VERSION
    mode: Literal["graph"] = "graph"
    enabled: bool = True
    updated_at: str | None = None
    applied_at: str | None = None
    source_hash: str = ""
    model_profiles: ModelProfileConfig = Field(default_factory=ModelProfileConfig)
    nodes: list[RuntimeNodeConfig] = Field(default_factory=list)
    edges: list[RuntimeGraphEdge] = Field(default_factory=list)
    node_order: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("enabled", mode="before")
    @classmethod
    def force_enabled(cls, value: bool) -> bool:
        """Runtime 始终保留一张可执行编排图，不能退回不可编排链路。"""

        return True


@dataclass(slots=True)
class RuntimeOrchestrationSnapshot:
    """当前进程中可直接读取的运行时编排快照。"""

    config: RuntimeGraphConfig
    valid: bool
    errors: tuple[str, ...] = ()
    path: Path = AGENT_ORCHESTRATION_CONFIG_PATH
    mtime_ns: int | None = None

    @property
    def graph_enabled(self) -> bool:
        """判断当前快照是否具备可执行编排图。"""

        return self.config.enabled and self.config.mode == "graph"


def default_graph_designer_payload() -> dict[str, Any]:
    """生成默认 Runtime 编排图的设计器兼容载荷。"""

    definitions = list_runtime_node_definitions()
    edges = [
        ("summary_history", "normalize_input", "下一步", "always"),
        ("normalize_input", "append_user_message", "下一步", "always"),
        ("append_user_message", "route", "进入场景路由", "always"),
        ("route", "persist", "已有直接回复", "has_auto_tasks"),
        ("route", "local_rag", "需要本地上下文", "needs_local_knowledge"),
        ("route", "direct_vision_reply", "视觉直答", "direct_vision_reply"),
        ("route", "extract", "进入任务理解", "always"),
        ("local_rag", "direct_vision_reply", "视觉直答", "direct_vision_reply"),
        ("local_rag", "extract", "带本地上下文理解", "always"),
        ("direct_vision_reply", "persist", "视觉回复完成", "has_auto_tasks"),
        ("direct_vision_reply", "extract", "视觉任务继续规划", "always"),
        ("extract", "plan", "任务流规划", "always"),
        ("plan", "execution_policy", "策略校验", "always"),
        ("execution_policy", "persist", "需要确认或直接回复", "has_auto_tasks"),
        ("execution_policy", "external_rag", "需要外部知识", "needs_external_rag"),
        ("execution_policy", "plan_tasks", "生成任务流", "always"),
        ("external_rag", "plan_tasks", "知识进入任务流", "always"),
        ("plan_tasks", "validate_tasks", "校验任务流", "always"),
        ("validate_tasks", "persist", "保存任务流", "always"),
    ]
    return {
        "version": GRAPH_CONFIG_VERSION,
        "model_profiles": {},
        "nodes": [
            {
                "id": definition.node_type,
                "node_type": definition.node_type,
                "module_id": definition.module_id,
                "label": definition.label,
                "phase": definition.phase,
                "enabled": True,
                "config": {},
            }
            for definition in definitions
        ],
        "edges": [
            {
                "id": f"{source}__{target}",
                "source": source,
                "target": target,
                "label": label,
                "condition": condition,
            }
            for source, target, label, condition in edges
        ],
    }


def default_graph_config(*, warnings: list[str] | None = None) -> RuntimeGraphConfig:
    """返回默认可编排 Agent 图配置。

    这张图就是 AutoGPT 的默认工作流。即使本地没有运行时配置文件，
    Pipeline 也会按这张图构建节点，而不是进入另一条隐藏不可编排链路。
    """

    payload = default_graph_designer_payload()
    nodes = normalize_runtime_nodes(payload["nodes"])
    edges = normalize_runtime_edges(payload["edges"], {node.id for node in nodes})
    node_order = validate_runtime_graph(nodes, edges)
    return RuntimeGraphConfig(
        mode="graph",
        enabled=True,
        source_hash=stable_designer_hash(payload),
        nodes=nodes,
        edges=edges,
        node_order=node_order,
        warnings=warnings or [],
    )


def stable_designer_hash(payload: dict[str, Any]) -> str:
    """生成设计器草稿的稳定哈希，用于判断草稿是否已经应用。"""

    comparable = {
        "version": payload.get("version", GRAPH_CONFIG_VERSION),
        "nodes": [
            {
                "id": node.get("id"),
                "node_type": node.get("node_type"),
                "module_id": node.get("module_id"),
                "label": node.get("label"),
                "phase": node.get("phase"),
                "enabled": node.get("enabled", True),
                "config": node.get("config") or {},
            }
            for node in payload.get("nodes", [])
            if isinstance(node, dict)
        ],
        "edges": [
            {
                "source": edge.get("source"),
                "target": edge.get("target"),
                "label": edge.get("label", ""),
                "condition": edge.get("condition", "always"),
                "scene": edge.get("scene"),
            }
            for edge in payload.get("edges", [])
            if isinstance(edge, dict)
        ],
        "model_profiles": payload.get("model_profiles") or {},
    }
    text = json.dumps(comparable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()


def build_graph_config_from_designer(payload: dict[str, Any], *, applied_at: str | None = None) -> RuntimeGraphConfig:
    """把管理端设计器草稿转换成可运行的图编排配置。

    Args:
        payload: 管理端保存的设计器草稿。
        applied_at: 本次应用配置的时间。

    Returns:
        RuntimeGraphConfig: 已校验并包含执行顺序的运行时配置。

    Raises:
        ValueError: 当草稿无法安全应用到 Runtime 时抛出。
    """

    nodes = normalize_runtime_nodes(payload.get("nodes", []))
    edges = normalize_runtime_edges(payload.get("edges", []), {node.id for node in nodes})
    enabled_nodes = [node for node in nodes if node.enabled]
    node_order = validate_runtime_graph(enabled_nodes, edges)
    return RuntimeGraphConfig(
        mode="graph",
        enabled=True,
        updated_at=payload.get("updated_at"),
        applied_at=applied_at,
        source_hash=stable_designer_hash(payload),
        model_profiles=ModelProfileConfig.model_validate(payload.get("model_profiles") or {}),
        nodes=nodes,
        edges=edges,
        node_order=node_order,
    )


def write_runtime_orchestration_config(config: RuntimeGraphConfig) -> None:
    """将运行时编排配置写入 resources/agent 资源目录。"""

    AGENT_ORCHESTRATION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    AGENT_ORCHESTRATION_CONFIG_PATH.write_text(
        json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_runtime_orchestration_config() -> RuntimeGraphConfig:
    """读取运行时编排配置，文件不存在时返回默认编排图。"""

    if not AGENT_ORCHESTRATION_CONFIG_PATH.exists():
        return default_graph_config()
    data = json.loads(AGENT_ORCHESTRATION_CONFIG_PATH.read_text(encoding="utf-8"))
    return RuntimeGraphConfig.model_validate(data)


def reload_runtime_orchestration_config(*, force: bool = False) -> RuntimeOrchestrationSnapshot:
    """重新加载运行时编排配置。

    Args:
        force: 是否忽略 mtime 缓存强制重读。

    Returns:
        RuntimeOrchestrationSnapshot: 当前进程中的最新快照。
    """

    return runtime_orchestration_store.reload(force=force)


def get_runtime_orchestration_snapshot() -> RuntimeOrchestrationSnapshot:
    """读取当前运行时编排快照，文件变更时自动热更新。"""

    return runtime_orchestration_store.get_snapshot()


def is_designer_applied_to_runtime(
    payload: dict[str, Any], snapshot: RuntimeOrchestrationSnapshot | None = None
) -> bool:
    """判断指定设计器草稿是否已经应用到运行时配置。"""

    snapshot = snapshot or get_runtime_orchestration_snapshot()
    return snapshot.valid and snapshot.graph_enabled and snapshot.config.source_hash == stable_designer_hash(payload)


class RuntimeOrchestrationStore:
    """维护当前进程内的编排配置快照，并支持 mtime 热更新。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._snapshot = RuntimeOrchestrationSnapshot(config=default_graph_config(), valid=True, path=path)

    def get_snapshot(self) -> RuntimeOrchestrationSnapshot:
        """在配置文件变更时自动重读，否则返回缓存快照。"""

        mtime_ns = self.current_mtime_ns()
        if mtime_ns != self._snapshot.mtime_ns:
            return self.reload(force=True)
        return self._snapshot

    def reload(self, *, force: bool = False) -> RuntimeOrchestrationSnapshot:
        """重新读取配置文件并更新缓存快照。"""

        mtime_ns = self.current_mtime_ns()
        if not force and mtime_ns == self._snapshot.mtime_ns:
            return self._snapshot
        try:
            config = read_runtime_orchestration_config()
            config.node_order = validate_runtime_graph([node for node in config.nodes if node.enabled], config.edges)
            self._snapshot = RuntimeOrchestrationSnapshot(
                config=config,
                valid=True,
                path=self.path,
                mtime_ns=mtime_ns,
            )
        except Exception as error:
            logger.warning(
                f"AutoGPT runtime orchestration config is invalid, fallback to default orchestration graph: {error}"
            )
            self._snapshot = RuntimeOrchestrationSnapshot(
                config=default_graph_config(warnings=["运行时配置无效，当前进程已临时使用默认编排图。"]),
                valid=False,
                errors=(str(error),),
                path=self.path,
                mtime_ns=mtime_ns,
            )
        return self._snapshot

    def current_mtime_ns(self) -> int | None:
        """读取运行时配置文件的修改时间。"""

        if not self.path.exists():
            return None
        return self.path.stat().st_mtime_ns


def normalize_runtime_nodes(raw_nodes: Any) -> list[RuntimeNodeConfig]:
    if not isinstance(raw_nodes, list):
        raise ValueError("Runtime graph nodes must be a list")

    nodes: list[RuntimeNodeConfig] = []
    seen_ids: set[str] = set()
    seen_types: set[str] = set()
    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            raise ValueError(f"Runtime graph node #{index + 1} must be an object")
        node_id = str(raw_node.get("id") or "").strip()
        node_type = str(raw_node.get("node_type") or raw_node.get("runtime_node_type") or node_id).strip()
        if not node_id:
            raise ValueError(f"Runtime graph node #{index + 1} is missing id")
        if node_id in seen_ids:
            raise ValueError(f"Runtime graph node id `{node_id}` is duplicated")
        if node_type in seen_types:
            raise ValueError(f"Runtime graph node type `{node_type}` cannot appear more than once")
        definition = RUNTIME_NODE_REGISTRY.get(node_type)
        if definition is None:
            raise ValueError(f"Runtime graph node `{node_id}` references unknown node type `{node_type}`")
        enabled = bool(raw_node.get("enabled", True))
        if definition.required and not enabled:
            raise ValueError(f"Runtime graph node `{node_type}` is required and cannot be disabled")
        seen_ids.add(node_id)
        seen_types.add(node_type)
        raw_config = raw_node.get("config")
        node_config: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}
        nodes.append(
            RuntimeNodeConfig(
                id=node_id,
                node_type=node_type,
                module_id=str(raw_node.get("module_id") or definition.module_id),
                label=str(raw_node.get("label") or definition.label),
                phase=str(raw_node.get("phase") or definition.phase),
                enabled=enabled,
                config=node_config,
                runtime_applied=enabled,
            )
        )
    return nodes


def normalize_runtime_edges(raw_edges: Any, node_ids: set[str]) -> list[RuntimeGraphEdge]:
    if not isinstance(raw_edges, list):
        raise ValueError("Runtime graph edges must be a list")

    edges: list[RuntimeGraphEdge] = []
    seen_edges: set[tuple[str, str]] = set()
    for index, raw_edge in enumerate(raw_edges):
        if not isinstance(raw_edge, dict):
            raise ValueError(f"Runtime graph edge #{index + 1} must be an object")
        source = str(raw_edge.get("source") or "").strip()
        target = str(raw_edge.get("target") or "").strip()
        if source not in node_ids or target not in node_ids:
            raise ValueError(f"Runtime graph edge #{index + 1} references missing nodes")
        if source == target:
            raise ValueError("Runtime graph edge cannot connect a node to itself")
        edge_key = (source, target)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        edges.append(
            RuntimeGraphEdge(
                id=str(raw_edge.get("id") or f"{source}__{target}"),
                source=source,
                target=target,
                label=str(raw_edge.get("label") or ""),
                condition=normalize_runtime_edge_condition(raw_edge.get("condition")),
                scene=normalize_runtime_edge_scene(raw_edge.get("scene")),
                runtime_applied=True,
            )
        )
    return edges


def normalize_runtime_edge_condition(value: Any) -> RuntimeEdgeCondition:
    """把设计器传入的边条件归一化为内置条件。"""

    allowed = {
        "always",
        "has_auto_tasks",
        "no_auto_tasks",
        "needs_local_knowledge",
        "needs_external_rag",
        "direct_vision_reply",
        "scene_chat",
        "scene_command",
        "scene_knowledge",
        "scene_vision",
        "scene_task",
        "scene_violation",
    }
    text = str(value or "always").strip()
    if text not in allowed:
        raise ValueError(f"Runtime graph edge condition `{text}` is not supported")
    return text  # type: ignore[return-value]


def normalize_runtime_edge_scene(value: Any) -> RuntimeScene | None:
    """把可选场景字段归一化为固定场景键。"""

    if value is None or value == "":
        return None
    text = str(value).strip()
    allowed = {"chat", "command", "knowledge", "vision", "task", "violation"}
    if text not in allowed:
        raise ValueError(f"Runtime graph edge scene `{text}` is not supported")
    return text  # type: ignore[return-value]


def validate_runtime_graph(nodes: list[RuntimeNodeConfig], edges: list[RuntimeGraphEdge]) -> list[str]:
    if not nodes:
        raise ValueError("Runtime graph must contain at least one enabled node")

    node_by_id = {node.id: node for node in nodes}
    enabled_ids = set(node_by_id)
    enabled_types = {node.node_type for node in nodes}
    missing_required = sorted(REQUIRED_RUNTIME_NODE_TYPES - enabled_types)
    if missing_required:
        raise ValueError(f"Runtime graph is missing required nodes: {', '.join(missing_required)}")

    active_edges = [edge for edge in edges if edge.source in enabled_ids and edge.target in enabled_ids]
    if len(nodes) > 1 and not active_edges:
        raise ValueError("Runtime graph must connect enabled nodes with edges")
    validate_single_entry_and_terminal(nodes, active_edges)
    order_ids = topological_sort_runtime_nodes(nodes, active_edges)
    order_types = [node_by_id[node_id].node_type for node_id in order_ids]
    validate_required_runtime_order(order_types)
    return order_types


def validate_single_entry_and_terminal(nodes: list[RuntimeNodeConfig], edges: list[RuntimeGraphEdge]) -> None:
    node_ids = {node.id for node in nodes}
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        incoming[edge.target] += 1
        outgoing[edge.source] += 1
    entries = [node_id for node_id, count in incoming.items() if count == 0]
    terminals = [node_id for node_id, count in outgoing.items() if count == 0]
    if len(entries) != 1:
        raise ValueError("Runtime graph must have exactly one entry node")
    if len(terminals) != 1:
        raise ValueError("Runtime graph must have exactly one terminal node")
    visited = reachable_from(entries[0], edges)
    if visited != node_ids:
        missing = ", ".join(sorted(node_ids - visited))
        raise ValueError(f"Runtime graph has disconnected nodes: {missing}")


def topological_sort_runtime_nodes(nodes: list[RuntimeNodeConfig], edges: list[RuntimeGraphEdge]) -> list[str]:
    definition_order = {node_type: index for index, node_type in enumerate(DEFAULT_RUNTIME_NODE_ORDER)}
    node_by_id = {node.id: node for node in nodes}
    incoming = {node.id: 0 for node in nodes}
    outgoing: dict[str, list[str]] = {node.id: [] for node in nodes}
    for edge in edges:
        incoming[edge.target] += 1
        outgoing[edge.source].append(edge.target)

    ready = sorted(
        [node_id for node_id, count in incoming.items() if count == 0],
        key=lambda node_id: definition_order.get(node_by_id[node_id].node_type, 999),
    )
    ordered: list[str] = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(node_id)
        for target in sorted(
            outgoing[node_id],
            key=lambda item: definition_order.get(node_by_id[item].node_type, 999),
        ):
            incoming[target] -= 1
            if incoming[target] == 0:
                ready.append(target)
                ready.sort(key=lambda item: definition_order.get(node_by_id[item].node_type, 999))
    if len(ordered) != len(nodes):
        raise ValueError("Runtime graph must not contain cycles")
    return ordered


def reachable_from(entry_id: str, edges: list[RuntimeGraphEdge]) -> set[str]:
    outgoing: dict[str, list[str]] = {}
    for edge in edges:
        outgoing.setdefault(edge.source, []).append(edge.target)
    visited = {entry_id}
    stack = [entry_id]
    while stack:
        node_id = stack.pop()
        for target in outgoing.get(node_id, []):
            if target in visited:
                continue
            visited.add(target)
            stack.append(target)
    return visited


def validate_required_runtime_order(node_types: list[str]) -> None:
    position = {node_type: index for index, node_type in enumerate(node_types)}
    for before, after in (
        ("normalize_input", "append_user_message"),
        ("append_user_message", "route"),
        ("route", "local_rag"),
        ("route", "direct_vision_reply"),
        ("route", "extract"),
        ("local_rag", "extract"),
        ("direct_vision_reply", "extract"),
        ("extract", "plan"),
        ("plan", "execution_policy"),
        ("execution_policy", "external_rag"),
        ("execution_policy", "plan_tasks"),
        ("external_rag", "plan_tasks"),
        ("plan_tasks", "validate_tasks"),
        ("validate_tasks", "persist"),
    ):
        if before in position and after in position and position[before] > position[after]:
            raise ValueError(f"Runtime graph requires `{before}` to run before `{after}`")


runtime_orchestration_store = RuntimeOrchestrationStore(AGENT_ORCHESTRATION_CONFIG_PATH)
