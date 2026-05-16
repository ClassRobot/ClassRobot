"""兼容旧路径的内置 Agent 导出。

历史代码会从 `utils.llm.agents.tools` 导入 `SummaryAgent`、`RagAgent`
等类。真实实现已经按职责移动到 `core.agent.builtin`，新代码不要
继续把 Agent 放进这个 `tools.py` 文件，避免再次出现 Agent / Tool 概念混用。
"""

from .builtin import AutoTaskAgent as AutoTaskAgent
from .builtin import ExtractAgent as ExtractAgent
from .builtin import FileAgent as FileAgent
from .builtin import LLMAgent as LLMAgent
from .builtin import RagAgent as RagAgent
from .builtin import SummaryAgent as SummaryAgent
from .builtin import VisionAgent as VisionAgent

__all__ = [
    "AutoTaskAgent",
    "ExtractAgent",
    "FileAgent",
    "LLMAgent",
    "RagAgent",
    "SummaryAgent",
    "VisionAgent",
]
