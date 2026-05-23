"""AutoGPT 运行时核心入口。

运行时包会被内置 Agent 在初始化阶段引用，因此这里保持轻量导出，避免
``builtin -> runtime -> util -> builtin`` 这类循环导入。需要具体对象时再
按名称懒加载对应模块。
"""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "AutoGPTHarness": ".harness",
    "AgentLoopConfig": ".loop",
    "AgentLoopDecision": ".loop",
    "CapabilityCatalog": ".loop",
    "ChatSession": ".util",
    "ChatSessionDepends": ".util",
    "ChatSessionManager": ".util",
    "CognitiveAgentLoop": ".loop",
    "LocalKnowledgeRetriever": ".knowledge",
    "LoopBudget": ".loop",
    "MessageProcessingPipeline": ".pipeline",
    "ObservationFact": ".loop",
    "RuntimeContext": ".knowledge",
    "RuntimeGraphExecutor": ".graph_executor",
    "SkillCatalog": ".knowledge",
    "TaskWorkflow": ".schema",
    "WorkflowBuilder": ".workflow",
    "WorkflowExecutor": ".workflow",
    "chat_session_manager": ".util",
    "markdown_to_message": ".util",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """按需加载运行时对象，避免包初始化阶段产生循环依赖。

    Args:
        name: 需要从运行时入口获取的对象名称。

    Returns:
        Any: 对应运行时模块导出的对象。

    Raises:
        AttributeError: 目标名称不是运行时公开入口。
    """

    if module_name := _EXPORTS.get(name):
        module = import_module(module_name, __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
