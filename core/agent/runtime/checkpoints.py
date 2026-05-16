"""兼容旧路径的工作流检查点导出。

真实实现位于 `core.agent.runtime.persistence.checkpoints`。新代码应从
`persistence` 子包导入，避免 AutoGPT 顶层再次堆积持久化实现。
"""

from .persistence.checkpoints import WorkflowCheckpointStore as WorkflowCheckpointStore
from .persistence.checkpoints import serialize_workflow as serialize_workflow

__all__ = [
    "WorkflowCheckpointStore",
    "serialize_workflow",
]
