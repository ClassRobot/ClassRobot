from re import sub
from asyncio import gather

from nonebot import logger

from pydantic import Field

from core.llm.message import Context
from utils.tools.cos import upload_file

from ..base import BaseAgent, BaseAgentConfig
from ..ragflow import AsyncRagFlow
from ..ragflow.client import ragflow_enabled
from ..ragflow.schema import Chunk, ChatBotMessage


class RagAgentConfig(BaseAgentConfig):
    """外部知识检索 Agent 的运行配置。"""


class RagAgent(BaseAgent):
    """负责调用 RagFlow 检索与学校、教育相关的补充知识。"""

    agent_name = "rag_agent"
    display_name = "外部知识检索智能体"
    capabilities = ("external_rag", "knowledge_retrieval")
    config: RagAgentConfig = Field(default_factory=RagAgentConfig)

    async def execute(self, messages: Context) -> str | None:
        """根据抽取上下文执行检索问答。

        Args:
            messages: 由抽取智能体生成的结构化上下文。

        Returns:
            str | None: 检索结果文本，不存在结果时返回 `None`。
        """
        if not ragflow_enabled:
            logger.warning("RagFlow is not configured; skip retrieval")
            return None
        try:
            rag_session = AsyncRagFlow()
            chatbots = await rag_session.get_chatbots()
            if not chatbots:
                logger.warning("RagFlow has no available chatbots")
                return None
            session = await chatbots[0].create_session()
            try:
                reply = await session.ask(question=messages.single_modal())
                if replace := await self.replace(reply):
                    return replace
            finally:
                await chatbots[0].delete_session([session.id])
        except Exception as error:
            logger.exception(error)
            return None
        return None

    async def replace(self, reply: ChatBotMessage) -> str | None:
        """将 RagFlow 回复中的引用标记替换为图片链接。

        Args:
            reply: RagFlow 返回的回复对象。

        Returns:
            str | None: 替换后的回复文本，不可用时返回 `None`。
        """
        if not reply.reference.chunks or reply.reference.total == 0 or not reply.answer or reply.answer == "null":
            return None
        answer = reply.answer
        upload_tasks = tuple(self.upload_file(ref) for ref in reply.reference.chunks)
        if not upload_tasks:
            return None
        urls = await gather(*upload_tasks)

        # RagFlow 会在答案里嵌入 `##0$$` 这类引用标记，这里替换成可发送图片。
        answer = sub(r"##(\d+)\$\$", lambda match: f"\n> 相关材料:\n> ![image]({urls[int(match.group(1))]})\n", answer)
        return answer

    async def upload_file(self, ref: Chunk) -> str:
        """上传检索引用中附带的图片资源。

        Args:
            ref: 检索引用对应的分块对象。

        Returns:
            str: 上传后的图片访问地址。
        """
        if image := await ref.get_image():
            return await upload_file(image, ref.image_id)
        return ""
