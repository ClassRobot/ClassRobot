from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.usefixtures("loaded_plugins")


def _node_registry():
    from src.core.agent.runtime.node_registry import (
        DEFAULT_RUNTIME_NODE_ORDER,
        REQUIRED_RUNTIME_NODE_TYPES,
        RUNTIME_NODE_REGISTRY,
    )

    return DEFAULT_RUNTIME_NODE_ORDER, REQUIRED_RUNTIME_NODE_TYPES, RUNTIME_NODE_REGISTRY


def _orchestration_config():
    from src.core.agent.runtime import orchestration_config

    return orchestration_config


def _designer_payload(node_types: tuple[str, ...] | None = None) -> dict:
    """生成一份符合管理端设计器结构的测试编排。"""

    default_node_order, _, runtime_node_registry = _node_registry()
    node_types = node_types or default_node_order
    nodes = []
    for index, node_type in enumerate(node_types):
        definition = runtime_node_registry[node_type]
        nodes.append(
            {
                "id": node_type,
                "node_type": node_type,
                "module_id": definition.module_id,
                "label": definition.label,
                "phase": definition.phase,
                "x": 80 + index * 16,
                "y": 80,
                "enabled": True,
                "config": {},
            }
        )
    return {
        "version": 1,
        "updated_at": "2026-05-15T00:00:00",
        "note": "测试编排",
        "nodes": nodes,
        "edges": [
            {"id": f"{source}__{target}", "source": source, "target": target, "label": "下一步"}
            for source, target in zip(node_types, node_types[1:])
        ],
    }


def _isolate_runtime_config(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """把运行时编排配置隔离到临时目录，避免污染本地配置。"""

    orchestration_config = _orchestration_config()
    runtime_path = tmp_path / "agent_orchestration_runtime.json"
    runtime_store = orchestration_config.RuntimeOrchestrationStore(runtime_path)
    monkeypatch.setattr(orchestration_config, "AGENT_ORCHESTRATION_CONFIG_PATH", runtime_path)
    monkeypatch.setattr(orchestration_config, "runtime_orchestration_store", runtime_store)
    return runtime_path


def test_build_graph_config_from_default_designer_payload():
    default_node_order, _, _ = _node_registry()
    orchestration_config = _orchestration_config()
    payload = orchestration_config.default_graph_designer_payload()

    config = orchestration_config.build_graph_config_from_designer(payload, applied_at="2026-05-15T00:00:01")

    assert config.mode == "graph"
    assert config.enabled is True
    assert config.applied_at == "2026-05-15T00:00:01"
    assert config.node_order == list(default_node_order)
    assert config.source_hash == orchestration_config.stable_designer_hash(payload)
    assert any(edge.condition == "has_auto_tasks" for edge in config.edges)
    assert any(edge.condition == "direct_vision_reply" for edge in config.edges)


def test_runtime_orchestration_config_path_lives_in_resources():
    orchestration_config = _orchestration_config()

    from src.platform.config import agent_resources_dir

    assert orchestration_config.AGENT_ORCHESTRATION_CONFIG_PATH == (
        agent_resources_dir / "agent_orchestration_runtime.json"
    )


def test_missing_runtime_config_uses_default_graph(monkeypatch, tmp_path):
    default_node_order, _, _ = _node_registry()
    orchestration_config = _orchestration_config()
    runtime_path = _isolate_runtime_config(monkeypatch, tmp_path)

    snapshot = orchestration_config.reload_runtime_orchestration_config(force=True)

    assert not runtime_path.exists()
    assert snapshot.valid is True
    assert snapshot.graph_enabled is True
    assert snapshot.config.mode == "graph"
    assert snapshot.config.node_order == list(default_node_order)
    assert snapshot.config.source_hash == orchestration_config.stable_designer_hash(
        orchestration_config.default_graph_designer_payload()
    )


def test_unsupported_runtime_config_falls_back_to_default_graph(monkeypatch, tmp_path):
    default_node_order, _, _ = _node_registry()
    orchestration_config = _orchestration_config()
    runtime_path = _isolate_runtime_config(monkeypatch, tmp_path)
    runtime_path.write_text(json.dumps({"mode": "fixed", "enabled": False}), encoding="utf-8")

    snapshot = orchestration_config.reload_runtime_orchestration_config(force=True)

    assert snapshot.valid is False
    assert snapshot.graph_enabled is True
    assert snapshot.config.mode == "graph"
    assert snapshot.config.node_order == list(default_node_order)
    assert snapshot.errors


def test_invalid_runtime_config_falls_back_to_default_graph(monkeypatch, tmp_path):
    default_node_order, _, _ = _node_registry()
    orchestration_config = _orchestration_config()
    runtime_path = _isolate_runtime_config(monkeypatch, tmp_path)
    runtime_path.write_text("{}", encoding="utf-8")

    snapshot = orchestration_config.reload_runtime_orchestration_config(force=True)

    assert snapshot.valid is False
    assert snapshot.graph_enabled is True
    assert snapshot.errors
    assert snapshot.config.node_order == list(default_node_order)


def test_build_graph_config_rejects_missing_required_node():
    default_node_order, _, _ = _node_registry()
    orchestration_config = _orchestration_config()
    node_types = tuple(node_type for node_type in default_node_order if node_type != "plan")

    with pytest.raises(ValueError, match="missing required nodes"):
        orchestration_config.build_graph_config_from_designer(_designer_payload(node_types))


def test_build_graph_config_rejects_duplicate_node_type():
    orchestration_config = _orchestration_config()
    payload = _designer_payload()
    duplicate = dict(payload["nodes"][0])
    duplicate["id"] = "summary_history_copy"
    payload["nodes"].append(duplicate)

    with pytest.raises(ValueError, match="cannot appear more than once"):
        orchestration_config.build_graph_config_from_designer(payload)


def test_build_graph_config_rejects_cycle():
    orchestration_config = _orchestration_config()
    payload = _designer_payload()
    payload["edges"].append({"source": "plan_tasks", "target": "extract", "label": "cycle"})

    with pytest.raises(ValueError, match="cycles"):
        orchestration_config.build_graph_config_from_designer(payload)


def test_stable_designer_hash_ignores_canvas_position_and_runtime_flags():
    orchestration_config = _orchestration_config()
    first = _designer_payload()
    second = _designer_payload()
    second["note"] = "只修改草稿说明"
    second["nodes"][0]["x"] = 999
    second["nodes"][0]["runtime_applied"] = True
    second["edges"][0]["runtime_applied"] = True

    assert orchestration_config.stable_designer_hash(first) == orchestration_config.stable_designer_hash(second)


def test_runtime_orchestration_store_reloads_written_config(monkeypatch, tmp_path):
    default_node_order, _, _ = _node_registry()
    orchestration_config = _orchestration_config()
    runtime_path = _isolate_runtime_config(monkeypatch, tmp_path)
    config = orchestration_config.build_graph_config_from_designer(_designer_payload())

    orchestration_config.write_runtime_orchestration_config(config)
    snapshot = orchestration_config.reload_runtime_orchestration_config(force=True)

    assert runtime_path.exists()
    assert snapshot.graph_enabled is True
    assert snapshot.config.node_order == list(default_node_order)


def test_runtime_orchestration_store_recomputes_node_order(monkeypatch, tmp_path):
    default_node_order, _, _ = _node_registry()
    orchestration_config = _orchestration_config()
    _isolate_runtime_config(monkeypatch, tmp_path)
    config = orchestration_config.build_graph_config_from_designer(_designer_payload())
    config.node_order = list(reversed(config.node_order))

    orchestration_config.write_runtime_orchestration_config(config)
    snapshot = orchestration_config.reload_runtime_orchestration_config(force=True)

    assert snapshot.graph_enabled is True
    assert snapshot.config.node_order == list(default_node_order)


def test_pipeline_build_nodes_uses_hot_reloaded_runtime_graph(monkeypatch, tmp_path, loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.llm.message import Messages
    from src.core.agent.runtime.harness import AutoGPTHarness
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    default_node_order, required_node_types, _ = _node_registry()
    orchestration_config = _orchestration_config()
    _isolate_runtime_config(monkeypatch, tmp_path)
    compact_node_order = tuple(node_type for node_type in default_node_order if node_type in required_node_types)
    config = orchestration_config.build_graph_config_from_designer(_designer_payload(compact_node_order))
    orchestration_config.write_runtime_orchestration_config(config)
    orchestration_config.reload_runtime_orchestration_config(force=True)

    harness = AutoGPTHarness.build(helpers=Helpers(), messages=Messages(), trace_id="autogpt-runtime-graph")
    pipeline = MessageProcessingPipeline(harness=harness)
    node_names = [type(node).__name__ for node in pipeline.build_nodes("你好")]

    assert node_names[0] == "NormalizeUserInputNode"
    assert "SummaryHistoryNode" not in node_names
    assert node_names[-1] == "PersistAssistantReplyNode"


def test_pipeline_build_nodes_uses_default_graph_without_config(monkeypatch, tmp_path, loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.llm.message import Messages
    from src.core.agent.runtime.harness import AutoGPTHarness
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline

    default_node_order, _, _ = _node_registry()
    orchestration_config = _orchestration_config()
    _isolate_runtime_config(monkeypatch, tmp_path)
    orchestration_config.reload_runtime_orchestration_config(force=True)

    harness = AutoGPTHarness.build(helpers=Helpers(), messages=Messages(), trace_id="autogpt-default-graph")
    pipeline = MessageProcessingPipeline(harness=harness)
    node_names = [type(node).__name__ for node in pipeline.build_nodes("你好")]

    assert len(node_names) == len(default_node_order)
    assert node_names[0] == "SummaryHistoryNode"
    assert node_names[-1] == "PersistAssistantReplyNode"


@pytest.mark.asyncio
async def test_runtime_graph_executor_takes_conditional_direct_reply_branch(loaded_plugins):
    from src.core.agent.runtime.schema import AutoTaskList
    from src.core.agent.runtime.coordination import PipelineState
    from src.core.agent.runtime.graph_executor import RuntimeGraphExecutor
    from src.core.agent.runtime.orchestration_config import default_graph_config

    visited: list[str] = []

    class StubNode:
        def __init__(self, node_type: str) -> None:
            self.node_type = node_type

        async def run(self, pipeline, state: PipelineState) -> None:
            visited.append(self.node_type)
            if self.node_type == "route":
                state.auto_tasks = AutoTaskList(reply="直接回复")

    class StubPipeline:
        trace_id = "autogpt-conditional"
        current_node_config = {}
        current_node_type = ""

        def build_node_from_config(self, node_config, message):
            return StubNode(node_config.node_type)

        def resolve_runtime_scene(self, state: PipelineState):
            return "chat"

        def needs_local_knowledge(self, route):
            return False

        def should_retrieve(self, route, plan):
            return False

        def should_direct_reply_from_vision(self, route, contents):
            return False

    await RuntimeGraphExecutor(default_graph_config()).run(StubPipeline(), PipelineState(), "你好")

    assert "route" in visited
    assert "persist" in visited
    assert "extract" not in visited


@pytest.mark.asyncio
async def test_runtime_graph_executor_uses_route_knowledge_sources_for_local_rag(loaded_plugins):
    from src.core.agent.runtime.schema import IntentRoute, KnowledgeSourceRequest
    from src.core.agent.runtime.coordination import PipelineState
    from src.core.agent.runtime.graph_executor import RuntimeGraphExecutor
    from src.core.agent.runtime.orchestration_config import default_graph_config

    visited: list[str] = []

    class StubNode:
        def __init__(self, node_type: str) -> None:
            self.node_type = node_type

        async def run(self, pipeline, state: PipelineState) -> None:
            visited.append(self.node_type)
            if self.node_type == "route":
                state.intent_route = IntentRoute(
                    intent="knowledge",
                    requires_command=False,
                    requires_rag=False,
                    reason="需要读取当前用户历史聊天",
                    knowledge_sources=[
                        KnowledgeSourceRequest(
                            source="user_chat_history",
                            query="之前让我记住的事情",
                            reason="用户追问历史上下文",
                        )
                    ],
                )

    class StubPipeline:
        trace_id = "autogpt-local-knowledge-route"
        current_node_config = {}
        current_node_type = ""

        def build_node_from_config(self, node_config, message):
            return StubNode(node_config.node_type)

        def resolve_runtime_scene(self, state: PipelineState):
            return "knowledge"

        def needs_local_knowledge(self, route):
            return bool(route and route.knowledge_sources)

        def should_retrieve(self, route, plan):
            return False

        def should_direct_reply_from_vision(self, route, contents):
            return False

    await RuntimeGraphExecutor(default_graph_config()).run(StubPipeline(), PipelineState(), "之前我让你记了什么")

    assert "route" in visited
    assert "local_rag" in visited


def test_pipeline_resolves_configured_model_profile(loaded_plugins):
    from src.platform.helper import Helpers
    from src.core.llm.message import Messages
    from src.core.agent.runtime.harness import AutoGPTHarness
    from src.core.agent.runtime.pipeline import MessageProcessingPipeline
    from src.core.agent.runtime.orchestration_config import ModelProfileConfig, default_graph_config

    harness = AutoGPTHarness.build(helpers=Helpers(), messages=Messages(), trace_id="autogpt-model-profile")
    pipeline = MessageProcessingPipeline(harness=harness)
    pipeline.runtime_graph_config = default_graph_config()
    pipeline.runtime_graph_config.model_profiles = ModelProfileConfig(supervisor_model="strong-model")
    pipeline.current_node_config = {"model_profile": "supervisor"}

    assert pipeline.resolve_model_name() == "strong-model"


def test_runtime_modules_are_imported_from_core_runtime():
    """运行时模块应直接从 core 运行时入口导入。"""

    import src.core.agent.runtime.knowledge as core_knowledge
    import src.core.agent.runtime.pipeline as core_pipeline
    import src.core.agent.runtime.orchestration_config as core_orchestration

    assert core_pipeline.__name__ == "src.core.agent.runtime.pipeline"
    assert core_orchestration.__name__ == "src.core.agent.runtime.orchestration_config"
    assert core_knowledge.__name__ == "src.core.agent.runtime.knowledge"
