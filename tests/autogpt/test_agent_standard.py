from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("loaded_plugins")


def test_base_agent_discovers_builtin_agents_by_inheritance():
    """Agent 发现应来自继承树，而不是散落的手写 list/dict。"""

    from src.core.agent import (
        RagAgent,
        BaseAgent,
        FileAgent,
        VisionAgent,
        ExtractAgent,
        SummaryAgent,
        AutoTaskAgent,
        ExecutionReplyAgent,
    )

    discovered = {agent_class.name(): agent_class for agent_class in BaseAgent.iter_agent_classes()}

    assert discovered["summary_agent"] is SummaryAgent
    assert discovered["extract_agent"] is ExtractAgent
    assert discovered["rag_agent"] is RagAgent
    assert discovered["file_agent"] is FileAgent
    assert discovered["vision_agent"] is VisionAgent
    assert discovered["auto_task_agent"] is AutoTaskAgent
    assert discovered["execution_reply_agent"] is ExecutionReplyAgent
    assert "tool_calling_agent" not in discovered
    assert "llm_agent" not in discovered
    assert BaseAgent.get_agent_class("summary_agent") is SummaryAgent
    assert isinstance(BaseAgent.create("summary_agent"), SummaryAgent)


def test_runtime_components_do_not_enter_agent_registry():
    """Runtime、Node、Retriever、Catalog 是组件，不是 Agent。"""

    from src.core.agent import BaseAgent
    from src.core.agent.runtime.pipeline import WorkflowNode
    from src.core.agent.runtime.node_registry import RuntimeNodeDefinition
    from src.core.agent.runtime.knowledge import SkillCatalog, RuntimeContext, LocalKnowledgeRetriever
    from src.core.agent.runtime.roles import RuntimeRoleCatalog, RuntimeRoleDescriptor, RuntimeRoleTraceRecord

    agent_classes = set(BaseAgent.iter_agent_classes())

    assert RuntimeRoleCatalog not in agent_classes
    assert RuntimeRoleDescriptor not in agent_classes
    assert RuntimeRoleTraceRecord not in agent_classes
    assert RuntimeContext not in agent_classes
    assert SkillCatalog not in agent_classes
    assert LocalKnowledgeRetriever not in agent_classes
    assert RuntimeNodeDefinition not in agent_classes
    assert WorkflowNode not in agent_classes
    assert not issubclass(WorkflowNode, BaseAgent)


def test_core_agent_suffix_classes_inherit_base_agent():
    """src.core.agent 中以 Agent 结尾的真实类必须继承 BaseAgent。"""

    from src.core.agent import BaseAgent
    import src.core.agent.agent as agent_module
    import src.core.agent.builtin.planning as planning_module
    import src.core.agent.builtin.retrieval as retrieval_module
    import src.core.agent.builtin.multimodal as multimodal_module
    import src.core.agent.builtin.conversation as conversation_module

    modules = (agent_module, conversation_module, multimodal_module, planning_module, retrieval_module)
    for module in modules:
        for _, value in inspect.getmembers(module, inspect.isclass):
            if not value.__name__.endswith("Agent"):
                continue
            assert issubclass(value, BaseAgent), f"{value.__module__}.{value.__name__} must inherit BaseAgent"


def test_builtin_agents_are_exported_from_new_entrypoints():
    """内置 Agent 只从新架构入口导出。"""

    from src.core.agent import builtin as builtin_module
    from src.core.agent import RagAgent, ExtractAgent, SummaryAgent, AutoTaskAgent, ExecutionReplyAgent

    assert builtin_module.SummaryAgent is SummaryAgent
    assert builtin_module.ExtractAgent is ExtractAgent
    assert builtin_module.RagAgent is RagAgent
    assert builtin_module.AutoTaskAgent is AutoTaskAgent
    assert builtin_module.ExecutionReplyAgent is ExecutionReplyAgent


def test_core_agent_entrypoints_export_builtin_agents():
    """核心入口应直接导出内置 Agent 实现。"""

    import src.core.agent as core_agent
    from src.core.agent import SummaryAgent
    from src.core.agent import SummaryAgent as CoreSummaryAgent

    assert not hasattr(core_agent, "ToolCallingAgent")
    assert not hasattr(core_agent, "LLMAgent")
    assert SummaryAgent is CoreSummaryAgent


def test_core_packages_do_not_import_removed_namespaces():
    """src.core 层不应反向依赖已经移除的旧命名空间。"""

    project_root = Path(__file__).resolve().parents[2]
    removed_prefixes = ("core.", "utils.", "src.features.", "src.plugins.application.active.autogpt.")
    for root in (project_root / "src" / "core" / "llm", project_root / "src" / "core" / "agent"):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imported_modules: list[str] = []
                if isinstance(node, ast.Import):
                    imported_modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules = [node.module]
                for module_name in imported_modules:
                    assert not module_name.startswith(removed_prefixes), f"{path} imports removed module {module_name}"


def test_builtin_agents_use_explicit_config_objects():
    """内置 Agent 必须显式暴露 config 对象，并兼容旧字段传参。"""

    from src.core.agent import BaseAgentConfig
    from src.core.agent.builtin import ExtractAgent, SummaryAgent, AutoTaskAgent

    summary = SummaryAgent(max_chars=128)
    assert isinstance(summary.config, BaseAgentConfig)
    assert summary.config.max_chars == 128
    assert summary.max_chars == 128

    extract_agent = ExtractAgent()
    assert isinstance(extract_agent.config, BaseAgentConfig)

    auto_task_agent = AutoTaskAgent(command_tools_prompt="命令目录", skill_catalog_prompt="技能目录")
    assert auto_task_agent.config.command_tools_prompt == "命令目录"
    assert auto_task_agent.config.skill_catalog_prompt == "技能目录"
