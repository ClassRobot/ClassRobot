"""AutoGPT 协调层组件。

该子包承载消息处理 Pipeline 的节点、运行态和本地确定性查询规则，
避免 `src/plugins/autogpt/` 顶层继续堆积大量 Python 文件。
"""

from .nodes import WorkflowNode as WorkflowNode
from .state import PipelineState as PipelineState
from .nodes import NormalizeUserInputNode as NormalizeUserInputNode
from .state import LocalChatStatisticsQuery as LocalChatStatisticsQuery
from .nodes import RUNTIME_NODE_CLASS_REGISTRY as RUNTIME_NODE_CLASS_REGISTRY
from .local_context import LocalContextQueryResolver as LocalContextQueryResolver
