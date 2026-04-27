from abc import ABC, abstractmethod

from utils.helper import Helpers
from pydantic import Field, BaseModel
from nonebot_plugin_alconna import UniMessage
from utils.llm.util import uni_message_to_contents
from utils.llm.message import Content, Context, Messages
from utils.llm.agents.tools import RagAgent, ExtractAgent, SummaryAgent, AutoTaskAgent

from .schema import ChatMessage, AutoTaskList


class PipelineState(BaseModel):
    """承载一次消息处理流程中的中间状态。"""

    user_content: list[Content] = Field(default_factory=list)
    extracted_context: Context | None = None
    retrieved_knowledge: str | None = None
    auto_tasks: AutoTaskList | None = None


class WorkflowNode(ABC):
    """定义工作流节点的统一接口。"""

    @abstractmethod
    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        """执行当前节点逻辑。"""


class SummaryHistoryNode(WorkflowNode):
    """在会话过长时先压缩历史消息。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        pipeline.messages = await SummaryAgent().execute(pipeline.messages)


class NormalizeUserInputNode(WorkflowNode):
    """把平台原始消息转换为统一内容结构。"""

    def __init__(self, message: str | UniMessage | ChatMessage) -> None:
        self.message = message

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        state.user_content = pipeline.normalize_message(self.message)


class AppendUserMessageNode(WorkflowNode):
    """把当前用户消息写入会话。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        pipeline.messages.user_message(state.user_content)


class ExtractContextNode(WorkflowNode):
    """从当前会话中抽取结构化上下文。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        state.extracted_context = await ExtractAgent().execute(pipeline.messages)


class RetrieveKnowledgeNode(WorkflowNode):
    """根据抽取上下文获取补充知识。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.extracted_context is None:
            return
        state.retrieved_knowledge = await RagAgent().execute(state.extracted_context)


class PlanTasksNode(WorkflowNode):
    """结合上下文、补充知识和命令清单生成最终规划。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.extracted_context is None:
            return
        state.auto_tasks = await AutoTaskAgent(
            helpers=pipeline.helpers,
            messages=pipeline.messages,
        ).execute(state.extracted_context, state.retrieved_knowledge)


class PersistAssistantReplyNode(WorkflowNode):
    """将结构化规划回写到会话历史，便于后续轮次继续引用。"""

    async def run(self, pipeline: "MessageProcessingPipeline", state: PipelineState) -> None:
        if state.auto_tasks is None:
            return
        pipeline.messages.assistant_message(pipeline.serialize_auto_task_result(state.auto_tasks))


class MessageProcessingPipeline:
    """封装 AI 会话主链路的标准处理流水线。"""

    def __init__(self, helpers: Helpers, messages: Messages) -> None:
        self.helpers = helpers
        self.messages = messages

    def normalize_message(self, message: str | UniMessage | ChatMessage) -> list[Content]:
        """将输入消息统一转换为内部内容结构。"""
        if isinstance(message, ChatMessage):
            return message.message
        return uni_message_to_contents(message)

    @staticmethod
    def serialize_auto_task_result(auto_tasks: AutoTaskList) -> str:
        """将自动任务结果序列化为会话中可追溯的统一格式。"""
        reply = (auto_tasks.reply or "").strip()
        task_json = auto_tasks.json(exclude={"reply", "create_at"}, ensure_ascii=False)
        if reply:
            return f"{reply}\n<hr/>\n{task_json}"
        return f"<hr/>\n{task_json}"

    def build_nodes(self, message: str | UniMessage | ChatMessage) -> list[WorkflowNode]:
        """构建当前轮次要执行的工作流节点列表。"""
        return [
            SummaryHistoryNode(),
            NormalizeUserInputNode(message),
            AppendUserMessageNode(),
            ExtractContextNode(),
            RetrieveKnowledgeNode(),
            PlanTasksNode(),
            PersistAssistantReplyNode(),
        ]

    async def process(self, message: str | UniMessage | ChatMessage) -> AutoTaskList | None:
        """执行完整消息处理流水线。"""
        state = PipelineState()
        for node in self.build_nodes(message):
            await node.run(self, state)
        return state.auto_tasks
