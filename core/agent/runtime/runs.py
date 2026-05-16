"""兼容旧路径的工作流运行记录导出。"""

from .persistence.runs import WorkflowRunStore as WorkflowRunStore

__all__ = [
    "WorkflowRunStore",
]
