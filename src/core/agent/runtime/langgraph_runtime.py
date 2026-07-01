from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, TypedDict

from nonebot import logger
from langgraph.graph import END, StateGraph

from .live_trace import agent_live_trace_registry
from .coordination import WorkflowNode, PipelineState
from .orchestration_config import RuntimeGraphEdge, RuntimeNodeConfig, RuntimeGraphConfig

if TYPE_CHECKING:
    from .pipeline import MessageProcessingPipeline


class LangGraphState(TypedDict):
    """LangGraph 运行时状态。

    项目内部仍使用强类型 ``PipelineState`` 承载业务状态，外层用 TypedDict
    适配 LangGraph 的状态图协议，避免把业务节点改造成框架专用写法。
    """

    state: PipelineState


class LangGraphEdgeRouter:
    """把项目运行时边条件转换为 LangGraph 条件边。"""

    def matches(
        self,
        edge: RuntimeGraphEdge,
        pipeline: "MessageProcessingPipeline",
        state: PipelineState,
    ) -> bool:
        """判断当前边是否满足运行条件。"""

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
            return state.auto_tasks is None and pipeline.should_direct_reply_from_vision(
                state.intent_route, state.user_content
            )
        if condition.startswith("scene_"):
            return scene == condition.removeprefix("scene_")
        return False


class LangGraphRuntime:
    """基于 LangGraph ``StateGraph`` 的 Agent 主运行时。

    该类是 AutoGPT 后续唯一主编排入口。节点实现仍复用当前项目的
    ``WorkflowNode``，这样可以先完成运行时迁移，再逐步删除旧自研图执行器。
    """

    def __init__(self, config: RuntimeGraphConfig) -> None:
        self.config = config
        self.router = LangGraphEdgeRouter()

    async def run(
        self,
        pipeline: "MessageProcessingPipeline",
        state: PipelineState,
        message,
    ) -> PipelineState:
        """编译并执行当前 LangGraph 图。"""

        graph = self.compile(pipeline, message)
        result = await graph.ainvoke({"state": state})
        return result["state"]

    def compile(self, pipeline: "MessageProcessingPipeline", message):
        """根据运行时配置编译 LangGraph 图。"""

        nodes = self.enabled_nodes_by_id()
        workflow = StateGraph(LangGraphState)
        for node_id, node_config in nodes.items():
            workflow.add_node(node_id, self.build_langgraph_node(pipeline, message, node_config))

        workflow.set_entry_point(self.entry_node_id(nodes))
        for node_id in nodes:
            outgoing = self.outgoing_edges(node_id, nodes)
            if not outgoing:
                workflow.add_edge(node_id, END)
                continue
            workflow.add_conditional_edges(
                node_id,
                self.build_edge_selector(pipeline, node_id, outgoing),
                {edge.target: edge.target for edge in outgoing} | {END: END},
            )
        return workflow.compile()

    def build_langgraph_node(
        self,
        pipeline: "MessageProcessingPipeline",
        message,
        node_config: RuntimeNodeConfig,
    ):
        """构造单个 LangGraph 节点函数。"""

        async def run_node(graph_state: LangGraphState) -> LangGraphState:
            state = graph_state["state"]
            node = pipeline.build_node_from_config(node_config, message)
            await self.run_workflow_node(pipeline, state, node_config, node)
            return {"state": state}

        run_node.__name__ = f"langgraph_node_{node_config.id}"
        return run_node

    def build_edge_selector(
        self,
        pipeline: "MessageProcessingPipeline",
        node_id: str,
        outgoing: list[RuntimeGraphEdge],
    ):
        """构造 LangGraph 条件边选择函数。"""

        def select_next(graph_state: LangGraphState) -> str:
            state = graph_state["state"]
            for edge in outgoing:
                if self.router.matches(edge, pipeline, state):
                    return edge.target
            return END

        select_next.__name__ = f"select_next_from_{node_id}"
        return select_next

    def enabled_nodes_by_id(self) -> dict[str, RuntimeNodeConfig]:
        """返回当前图中启用的节点映射。"""

        return {node.id: node for node in self.config.nodes if node.enabled}

    def entry_node_id(self, nodes: dict[str, RuntimeNodeConfig]) -> str:
        """解析图入口节点。"""

        incoming = {node_id: 0 for node_id in nodes}
        for edge in self.active_edges(nodes):
            incoming[edge.target] += 1
        entries = [node_id for node_id, count in incoming.items() if count == 0]
        if len(entries) != 1:
            raise ValueError("LangGraph runtime must have exactly one entry node")
        return entries[0]

    def outgoing_edges(self, node_id: str, nodes: dict[str, RuntimeNodeConfig]) -> list[RuntimeGraphEdge]:
        """按配置顺序返回指定节点的可用出边。"""

        return [
            edge
            for edge in self.config.edges
            if edge.source == node_id and edge.source in nodes and edge.target in nodes
        ]

    def active_edges(self, nodes: dict[str, RuntimeNodeConfig]) -> list[RuntimeGraphEdge]:
        """返回两端节点都启用的边。"""

        return [edge for edge in self.config.edges if edge.source in nodes and edge.target in nodes]

    async def run_workflow_node(
        self,
        pipeline: "MessageProcessingPipeline",
        state: PipelineState,
        node_config: RuntimeNodeConfig,
        node: WorkflowNode,
    ) -> None:
        """执行单个业务节点并记录可观测事件。"""

        node_name = node.__class__.__name__
        started_at = perf_counter()
        stage = pipeline.stage_from_node_type(node_config.node_type)
        logger.debug(f'AutoGPT trace "{pipeline.trace_id}" LangGraph node "{node_name}" started')
        agent_live_trace_registry.emit(
            pipeline.trace_id,
            event_type="node_entered",
            stage=stage,
            node_type=node_config.node_type,
            node_label=node_name,
            status="running",
            params_preview={
                "runtime": "langgraph",
                "node_id": node_config.id,
                "node_type": node_config.node_type,
                "config": node_config.config,
            },
        )
        previous_node_config = pipeline.current_node_config
        previous_node_type = pipeline.current_node_type
        pipeline.current_node_config = node_config.config
        pipeline.current_node_type = node_config.node_type
        try:
            await node.run(pipeline, state)
        except Exception as error:
            duration_ms = (perf_counter() - started_at) * 1000
            agent_live_trace_registry.emit(
                pipeline.trace_id,
                event_type="node_failed",
                stage=stage,
                node_type=node_config.node_type,
                node_label=node_name,
                status="failed",
                params_preview={"runtime": "langgraph", "node_id": node_config.id},
                error=error,
                duration_ms=duration_ms,
            )
            logger.exception(
                f'AutoGPT trace "{pipeline.trace_id}" LangGraph node "{node_name}" failed '
                f"in {duration_ms:.2f}ms: {error}"
            )
            raise
        finally:
            pipeline.current_node_config = previous_node_config
            pipeline.current_node_type = previous_node_type

        duration_ms = (perf_counter() - started_at) * 1000
        agent_live_trace_registry.emit(
            pipeline.trace_id,
            event_type="node_completed",
            stage=stage,
            node_type=node_config.node_type,
            node_label=node_name,
            status="completed",
            params_preview={
                "runtime": "langgraph",
                "scene": pipeline.resolve_runtime_scene(state),
                "has_route": state.intent_route is not None,
                "has_plan": state.agent_plan is not None,
                "tasks": len(state.auto_tasks.tasks) if state.auto_tasks else 0,
            },
            duration_ms=duration_ms,
        )
        logger.debug(
            f'AutoGPT trace "{pipeline.trace_id}" LangGraph node "{node_name}" finished in {duration_ms:.2f}ms'
        )


__all__ = ["LangGraphRuntime", "LangGraphState"]
