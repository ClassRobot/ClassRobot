"""项目内置 Agent 实现集合。

这里的类都必须继承 `BaseAgent` 或 `BaseFunctionAgent`。业务代码应从
本包或 `src.core.agent` 的统一导出中导入内置 Agent。
"""

from .retrieval import RagAgent as RagAgent
from .multimodal import FileAgent as FileAgent
from .multimodal import VisionAgent as VisionAgent
from .planning import AutoTaskAgent as AutoTaskAgent
from .conversation import ExtractAgent as ExtractAgent
from .conversation import SummaryAgent as SummaryAgent
from .conversation import ExecutionReplyAgent as ExecutionReplyAgent

__all__ = [
    "AutoTaskAgent",
    "ExecutionReplyAgent",
    "ExtractAgent",
    "FileAgent",
    "RagAgent",
    "SummaryAgent",
    "VisionAgent",
]
