"""AutoGPT 协调层组件。

该子包承载消息处理 Pipeline 的节点和运行态，
避免 `src/plugins/application/active/autogpt/` 顶层继续堆积大量 Python 文件。
"""

from .nodes import WorkflowNode as WorkflowNode
from .state import PipelineState as PipelineState
from .nodes import NormalizeUserInputNode as NormalizeUserInputNode
from .nodes import RUNTIME_NODE_CLASS_REGISTRY as RUNTIME_NODE_CLASS_REGISTRY
