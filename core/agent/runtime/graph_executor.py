from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from nonebot import logger

from .coordination import PipelineState, WorkflowNode
from .orchestration_config import RuntimeGraphEdge, RuntimeGraphConfig, RuntimeNodeConfig

if TYPE_CHECKING:
    from .pipeline import MessageProcessingPipeline


class RuntimeEdgeConditionEvaluator:
    """判断运行时编排图中的边是否满足当前轮次状态。"""

    def matches(
        self,
        edge: RuntimeGraphEdge,
        pipeline: "MessageProcessingPipeline",
        state: PipelineState,
    ) -> bool:
        """返回当前边是否可以被执行器选择。"""

        scene = pipeline.resolve_runtime_scene(state)
        if edge.scene is not None and edge.scene != scene:
            return False

        condition = edge.condition
        if condition == "always":
            return True
        if condition == "has_auto_tasks":
            return state.auto_tasks is not None
        if condition == "no_auto_tasks":
            return state.auto_tasks is None
        if condition == "needs_local_knowledge":
            return state.auto_tasks is None and pipeline.needs_local_knowledge(state.intent_route)
        if condition == "needs_external_rag":
            return (
                state.auto_tasks is None
                and state.extracted_context is not None
                and pipeline.should_retrieve(state.intent_route, state.agent_plan)
            )
        if condition == "direct_vision_reply":
            return (
                state.auto_tasks is None
                and pipeline.should_direct_reply_from_vision(state.intent_route, state.user_content)
            )
        if condition.startswith("scene_"):
            return scene == condition.removeprefix("scene_")
        return False


class RuntimeGraphExecutor:
    """按开发者配置的运行时编排图执行 Pipeline 节点。"""

    def __init__(self, config: RuntimeGraphConfig) -> None:
        self.config = config
        self.condition_evaluator = RuntimeEdgeConditionEvaluator()

    async def run(
        self,
        pipeline: "MessageProcessingPipeline",
        state: PipelineState,
        message,
    ) -> None:
        """从入口节点开始按条件边执行，直到没有可选下一跳。"""

        nodes = self.enabled_nodes_by_id()
        current_id = self.entry_node_id(nodes)
        executed = 0
        max_steps = max(len(nodes) + len(self.config.edges), 1)

        while current_id is not None:
            if executed > max_steps:
                raise ValueError("Runtime graph execution exceeded maximum steps")
            node_config = nodes[current_id]
            node = pipeline.build_node_from_config(node_config, message)
            await self.run_node(pipeline, state, node_config, node)
            current_id = self.next_node_id(current_id, pipeline, state)
            executed += 1

    def enabled_nodes_by_id(self) -> dict[str, RuntimeNodeConfig]:
        """返回当前图中启用的节点映射。"""

        return {node.id: node for node in self.config.nodes if node.enabled}

    def entry_node_id(self, nodes: dict[str, RuntimeNodeConfig]) -> str:
        """解析运行时图入口节点。"""

        incoming = {node_id: 0 for node_id in nodes}
        for edge in self.active_edges(nodes):
            incoming[edge.target] += 1
        entries = [node_id for node_id, count in incoming.items() if count == 0]
        if len(entries) != 1:
            raise ValueError("Runtime graph must have exactly one entry node")
        return entries[0]

    def next_node_id(
        self,
        current_id: str,
        pipeline: "MessageProcessingPipeline",
        state: PipelineState,
    ) -> str | None:
        """根据当前状态选择下一条满足条件的边。"""

        nodes = self.enabled_nodes_by_id()
        for edge in self.outgoing_edges(current_id, nodes):
            if self.condition_evaluator.matches(edge, pipeline, state):
                return edge.target
        return None

    def outgoing_edges(self, node_id: str, nodes: dict[str, RuntimeNodeConfig]) -> list[RuntimeGraphEdge]:
        """按配置顺序返回某节点的可用出边。"""

        return [
            edge
            for edge in self.config.edges
            if edge.source == node_id and edge.source in nodes and edge.target in nodes
        ]

    def active_edges(self, nodes: dict[str, RuntimeNodeConfig]) -> list[RuntimeGraphEdge]:
        """返回两端节点都启用的边。"""

        return [edge for edge in self.config.edges if edge.source in nodes and edge.target in nodes]

    async def run_node(
        self,
        pipeline: "MessageProcessingPipeline",
        state: PipelineState,
        node_config: RuntimeNodeConfig,
        node: WorkflowNode,
    ) -> None:
        """执行单个节点并记录运行日志。"""

        node_name = node.__class__.__name__
        started_at = perf_counter()
        logger.debug(f'AutoGPT trace "{pipeline.trace_id}" node "{node_name}" started')
        previous_node_config = pipeline.current_node_config
        previous_node_type = pipeline.current_node_type
        pipeline.current_node_config = node_config.config
        pipeline.current_node_type = node_config.node_type
        try:
            await node.run(pipeline, state)
        except Exception as error:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.exception(
                f'AutoGPT trace "{pipeline.trace_id}" node "{node_name}" failed in {duration_ms:.2f}ms: {error}'
            )
            raise
        finally:
            pipeline.current_node_config = previous_node_config
            pipeline.current_node_type = previous_node_type
        duration_ms = (perf_counter() - started_at) * 1000
        logger.debug(f'AutoGPT trace "{pipeline.trace_id}" node "{node_name}" finished in {duration_ms:.2f}ms')
