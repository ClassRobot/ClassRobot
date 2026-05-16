from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeNodeDefinition:
    """描述一个可被 AutoGPT Runtime 编排的节点。"""

    node_type: str
    label: str
    phase: str
    module_id: str
    description: str
    source: str
    order: int
    required: bool = False
    allow_disable: bool = True
    model_role: str | None = None


RUNTIME_NODE_DEFINITIONS: tuple[RuntimeNodeDefinition, ...] = (
    RuntimeNodeDefinition(
        node_type="summary_history",
        label="SummaryHistory",
        phase="压缩",
        module_id="pipeline",
        description="在会话过长时压缩历史，避免上下文无限增长。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=10,
        model_role="summary",
    ),
    RuntimeNodeDefinition(
        node_type="normalize_input",
        label="NormalizeUserInput",
        phase="输入",
        module_id="pipeline",
        description="把平台原始消息转换为统一的文本、图片和文件内容结构。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=20,
        required=True,
        allow_disable=False,
    ),
    RuntimeNodeDefinition(
        node_type="append_user_message",
        label="AppendUserMessage",
        phase="会话",
        module_id="pipeline",
        description="把本轮用户消息写入 Agent 会话上下文。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=30,
        required=True,
        allow_disable=False,
    ),
    RuntimeNodeDefinition(
        node_type="local_chat_statistics",
        label="LocalChatStatistics",
        phase="本地查询",
        module_id="pipeline",
        description="直接回答当前用户或当前系统群的聊天条数统计。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=40,
    ),
    RuntimeNodeDefinition(
        node_type="local_context",
        label="LocalContextQuery",
        phase="本地查询",
        module_id="pipeline",
        description="优先把身份、班级、课表等确定性问题路由到项目命令。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=50,
    ),
    RuntimeNodeDefinition(
        node_type="route",
        label="IntentRoute",
        phase="路由",
        module_id="pipeline",
        description="判断普通聊天、知识检索、命令、多步任务、视觉文件或违规场景。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=60,
        required=True,
        allow_disable=False,
        model_role="supervisor",
    ),
    RuntimeNodeDefinition(
        node_type="local_rag",
        label="RetrieveLocalKnowledge",
        phase="本地 RAG",
        module_id="local_knowledge",
        description="按需检索当前用户或当前系统群允许访问的聊天记录和文件空间。",
        source="src/plugins/autogpt/knowledge.py",
        order=70,
    ),
    RuntimeNodeDefinition(
        node_type="direct_vision_reply",
        label="DirectVisionReply",
        phase="视觉",
        module_id="pipeline",
        description="对无需命令和知识检索的简单图片问题直接调用多模态模型回复。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=80,
        model_role="vision",
    ),
    RuntimeNodeDefinition(
        node_type="extract",
        label="ExtractContext",
        phase="理解",
        module_id="pipeline",
        description="从当前会话中抽取目标、约束、对象和关键上下文。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=90,
        required=True,
        allow_disable=False,
        model_role="worker",
    ),
    RuntimeNodeDefinition(
        node_type="plan",
        label="Planner",
        phase="规划",
        module_id="policy_harness",
        description="把抽取结果转换成显式目标、风险、缺失信息和候选能力。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=100,
        required=True,
        allow_disable=False,
        model_role="supervisor",
    ),
    RuntimeNodeDefinition(
        node_type="execution_policy",
        label="ExecutionPolicy",
        phase="策略",
        module_id="policy_harness",
        description="用代码规则兜底高风险、缺参数和不可执行命令，防止模型越权。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=110,
        required=True,
        allow_disable=False,
    ),
    RuntimeNodeDefinition(
        node_type="external_rag",
        label="RetrieveKnowledge",
        phase="外部知识",
        module_id="local_knowledge",
        description="当计划明确需要知识库时调用外部 RAG，并在失败时降级。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=120,
        model_role="worker",
    ),
    RuntimeNodeDefinition(
        node_type="plan_tasks",
        label="PlanTasks",
        phase="任务",
        module_id="command_tools",
        description="结合计划、命令目录、Skill 和检索上下文生成可执行任务。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=130,
        required=True,
        allow_disable=False,
        model_role="supervisor",
    ),
    RuntimeNodeDefinition(
        node_type="validate_tasks",
        label="ValidateAutoTasks",
        phase="校验",
        module_id="command_tools",
        description="校验任务仍在当前用户可见、可调用的命令能力范围内。",
        source="src/plugins/autogpt/coordination/nodes.py",
        order=140,
        required=True,
        allow_disable=False,
    ),
    RuntimeNodeDefinition(
        node_type="persist",
        label="PersistAssistantReply",
        phase="收尾",
        module_id="pipeline",
        description="把结构化规划或回复写回会话历史，供后续轮次继续引用。",
        source="src/plugins/autogpt/pipeline.py",
        order=150,
        required=True,
        allow_disable=False,
    ),
)

RUNTIME_NODE_REGISTRY = {item.node_type: item for item in RUNTIME_NODE_DEFINITIONS}
DEFAULT_RUNTIME_NODE_ORDER = tuple(
    item.node_type for item in sorted(RUNTIME_NODE_DEFINITIONS, key=lambda item: item.order)
)
REQUIRED_RUNTIME_NODE_TYPES = frozenset(item.node_type for item in RUNTIME_NODE_DEFINITIONS if item.required)


def get_runtime_node_definition(node_type: str) -> RuntimeNodeDefinition | None:
    """按节点类型读取 Runtime 节点定义。"""

    return RUNTIME_NODE_REGISTRY.get(node_type)


def list_runtime_node_definitions() -> tuple[RuntimeNodeDefinition, ...]:
    """返回按默认执行顺序排列的 Runtime 节点定义。"""

    return tuple(sorted(RUNTIME_NODE_DEFINITIONS, key=lambda item: item.order))
