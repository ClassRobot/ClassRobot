from re import sub
from asyncio import gather

from nonebot import logger
from pydantic import Field
from openai import BaseModel
from httpx import AsyncClient
from utils.llm import client_create
from utils.config import autogpt_dir
from utils.skills import document_to_image_skill
from utils.llm.util import json_loads
from utils.helper.schema import Helpers
from utils.tools.cos import upload_file
from utils.template.prompts import Prompt
from utils.llm.agents.ragflow.schema import Chunk, ChatBotMessage

from .ragflow import AsyncRagFlow
from ..message import Content, Context, LLMRole
from .base import Messages, BaseAgent, BaseFunctionAgent


class VisionAgent(BaseFunctionAgent):
    """负责将图片内容交给多模态模型分析，并提取用户关心的信息。"""

    roles: set[LLMRole] = {LLMRole.system}
    """引用哪个Role消息"""

    class Params(BaseModel):
        """描述图片识别工具需要的输入参数。"""
        desc: str = Field(description="描述想要从图片中了解什么信息")
        urls: list[str] = Field(description="一个或多个图片url")

    @classmethod
    def name(cls) -> str:
        """返回视觉工具智能体的注册名称。"""
        return "vision_agent"

    async def execute(self, messages: Messages) -> Messages:
        """处理视觉工具调用，并把识别结果写回消息列表。

        参数:
            messages (Messages): 当前会话的消息集合。

        返回:
            Messages: 写入视觉识别结果后的消息集合。
        """
        print(self.name())
        vision_message = messages.get(*self.roles)  # 提取需要的消息
        for tool in self.call_tools(messages):
            params = self.Params.parse_raw(tool.function.arguments)
            contents: list[Content] = [Content(type="text", value=params.desc)]
            contents.extend(Content(type="image", value=url) for url in params.urls)
            vision_message.user_message(contents)
            response = await client_create(vision_message, multi_modal=True)  # 将识别后的结果返回给message
            messages.tool_message(tool.id, response.choices[0].message.content or "")
        return messages


class FileAgent(BaseFunctionAgent):
    """负责将文档转为图片后交给多模态模型解析内容。"""

    roles: set[LLMRole] = {LLMRole.system}
    """引用哪个Role消息"""

    class Params(BaseModel):
        """描述文件解析工具需要的输入参数。"""
        desc: str = Field(description="描述想要从文件中了解什么信息")
        urls: list[str] = Field(description="一个或多个文件url")

    @classmethod
    def name(cls) -> str:
        """返回文件工具智能体的注册名称。"""
        return "file_agent"

    async def execute(self, messages: Messages) -> Messages:
        """处理文件解析工具调用，并将结果写回消息列表。

        参数:
            messages (Messages): 当前会话的消息集合。

        返回:
            Messages: 写入文件解析结果后的消息集合。
        """
        print(self.name())
        images = []
        file_message = messages.get(*self.roles)  # 提取需要的消息

        async with AsyncClient() as client:
            for tool in self.call_tools(messages):
                params = self.Params.parse_raw(tool.function.arguments)
                for url in params.urls:
                    response = await client.get(url)
                    # Office/PDF files are first normalized into images so the same
                    # multimodal pipeline can inspect every page uniformly.
                    file_to_image = await document_to_image_skill.convert(response.content, save_path=autogpt_dir)
                    images.extend(file_to_image.images)
                if images:
                    contents: list[Content] = [Content(type="text", value=params.desc)]
                    contents.extend(Content(type="image", value=url) for url in file_to_image.images)
                    file_message.user_message(contents)
                    response = await client_create(file_message, multi_modal=True)
                    messages.tool_message(tool.id, response.choices[0].message.content or "")
                else:
                    messages.tool_message(tool.id, "解析失败:\n改文件过大或者文件类型不正确，只能识别，ppt、doc、pdf类型的文件")
        return messages


class LLMAgent(BaseAgent):
    """负责协调大模型对话与工具调用流程的智能体。"""

    @classmethod
    def name(cls) -> str:
        """返回当前智能体的注册名称。

        返回:
            str: 当前智能体在工具注册表中的唯一名称。
        """
        return "llm_agent"

    async def execute(self, messages: Messages) -> Messages:
        """执行当前逻辑。

        参数:
            messages (Messages): 消息列表。

        返回:
            Messages: 返回处理结果。
        """
        if messages[-1].role == LLMRole.assistant:
            return messages
        response = await client_create(messages, self.functions(), multi_modal=False)
        if response.choices[0].message.tool_calls:
            messages.add_tool(response.choices[0].message)
        else:
            messages.assistant_message(response.choices[0].message.content or "")
        return messages


class SummaryAgent(BaseAgent):
    """负责在会话过长时压缩历史对话，控制上下文长度。"""

    max_chars: int = 20480
    """最大字符数"""

    @classmethod
    def name(cls) -> str:
        """返回总结智能体的注册名称。"""
        return "summary_agent"

    async def execute(self, messages: Messages) -> Messages:
        """在消息过长时生成历史摘要并替换旧对话。

        参数:
            messages (Messages): 当前会话的消息集合。

        返回:
            Messages: 可能已被摘要压缩过的消息集合。
        """
        message_chars = messages.char_length()
        print(self.name(), message_chars)
        if message_chars > self.max_chars:
            system_message = messages.get(LLMRole.system)
            summary_message = messages.get(LLMRole.user, LLMRole.assistant)  # 提取需要的消息
            summary_message.user_message("针对之前的聊天内容进行总结,总结长度不超过<4000字.")
            response = await client_create(summary_message, multi_modal=True, max_tokens=4096)
            summary_text = response.choices[0].message.content or ""
            # Keep the original system prompt, but collapse the long-running dialogue
            # into a single assistant summary to cap token growth across sessions.
            messages.clear()
            messages.extend(system_message)
            messages.assistant_message("# 历史聊天内容总结\n" + summary_text)
        return messages


class ExtractAgent(BaseAgent):
    """负责从聊天历史中提取结构化上下文，供检索与任务规划使用。"""

    @classmethod
    def name(cls) -> str:
        """返回信息抽取智能体的注册名称。"""
        return "extract_agent"

    async def execute(self, messages: Messages):
        """将历史消息压缩为结构化上下文对象。

        参数:
            messages (Messages): 当前会话的消息集合。

        返回:
            Context: 从历史消息中抽取出的结构化上下文。
        """
        print(self.name())
        extract = Prompt("extract")
        # Extraction compresses free-form dialogue into a structured context that can
        # be shared by retrieval and task planning without replaying all history.
        self.messages.system_message(await extract.render({"history": self.message_to_string(messages)}))
        response = await client_create(self.messages, multi_modal=False, max_tokens=4096)
        text = response.choices[0].message.content or ""
        print(text)
        return Context.parse_obj(json_loads(text))

    def message_to_string(self, messages: Messages) -> str:
        """将系统、用户和助手消息序列化为字符串。

        参数:
            messages (Messages): 当前会话的消息集合。

        返回:
            str: 适合放入提示词中的 JSON 字符串。
        """
        message = messages.get(LLMRole.system, LLMRole.user, LLMRole.assistant)
        return message.json(ensure_ascii=False)


class RagAgent(BaseAgent):
    """负责调用 RagFlow 检索与学校、教育相关的补充知识。"""

    @classmethod
    def name(cls) -> str:
        """返回检索智能体的注册名称。"""
        return "rag_agent"

    async def execute(self, messages: Context) -> str | None:
        """根据抽取上下文执行检索问答。

        参数:
            messages (Context): 由抽取智能体生成的结构化上下文。

        返回:
            str | None: 检索结果文本，不存在结果时返回 `None`。
        """
        try:
            rag_session = AsyncRagFlow()
            chatbots = await rag_session.get_chatbots()
            session = await chatbots[0].create_session()
            try:
                reply = await session.ask(question=messages.single_modal())
                if replace := await self.replace(reply):
                    return replace
            finally:
                await chatbots[0].delete_session([session.id])
        except Exception as e:
            logger.exception(e)
            return None

    async def replace(self, reply: ChatBotMessage) -> str | None:
        """将 RagFlow 回复中的引用标记替换为图片链接。

        参数:
            reply (ChatBotMessage): RagFlow 返回的回复对象。

        返回:
            str | None: 替换后的回复文本，不可用时返回 `None`。
        """
        if not reply.reference.chunks or reply.reference.total == 0 or not reply.answer or reply.answer == "null":
            return None
        print(reply.answer)
        answer = reply.answer
        if not (urls := tuple(self.upload_file(ref) for ref in reply.reference.chunks)):
            return None
        print(urls)
        urls = await gather(*urls)

        # RagFlow answers embed reference markers like `##0$$`; replace them with
        # uploaded images so the final markdown can be sent back directly.
        answer = sub(r"##(\d+)\$\$", lambda m: f"\n> 相关材料:\n> ![image]({urls[int(m.group(1))]})\n", answer)
        return answer

    async def upload_file(self, ref: Chunk) -> str:
        """上传检索引用中附带的图片资源。

        参数:
            ref (Chunk): 检索引用对应的分块对象。

        返回:
            str: 上传后的图片访问地址。
        """
        if image := await ref.get_image():
            return await upload_file(image, ref.image_id)
        return ""


class AutoTaskAgent(BaseAgent):
    """负责结合帮助信息和聊天上下文生成自动任务建议。"""

    helpers: Helpers

    @classmethod
    def name(cls) -> str:
        """返回自动任务智能体的注册名称。"""
        return "auto_task_agent"

    async def execute(self, context: Context) -> str | None:
        """根据上下文生成自动任务规划结果。

        参数:
            context (Context): 由抽取智能体生成的结构化上下文。

        返回:
            str | None: 模型生成的任务规划结果文本。
        """
        messages = self.messages.get(LLMRole.system)
        # Task planning only sees the helper-constrained system prompt plus the chat
        # history, which keeps generated commands aligned with real plugin abilities.
        messages.system_message(await Prompt("auto_task").render({"helpers": self.helpers}))
        messages.extend(self.messages.get(LLMRole.user, LLMRole.assistant))
        print(messages)
        response = await client_create(messages)
        return response.choices[0].message.content
