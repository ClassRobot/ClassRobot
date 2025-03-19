from pydantic import Field
from openai import BaseModel
from httpx import AsyncClient
from utils.llm import client_create
from utils.config import autogpt_dir
from utils.tools.docs2img import File2Image
from utils.schemes.auto_task import AutoTaskList

from ..message import Role, Content
from .base import Messages, BaseAgent, BaseFunctionAgent


class VisionAgent(BaseFunctionAgent):
    """机器人视觉模块,可以帮助机器人识别图片中获取想要的信息,但该功能不负责处理任何图片本身信息,比如P图绘画等功能无法通过这个函数实现."""

    roles: set[Role] = {Role.system}
    """引用哪个Role消息"""

    class Params(BaseModel):
        desc: str = Field(description="描述想要从图片中了解什么信息")
        urls: list[str] = Field(description="一个或多个图片url")

    @classmethod
    def name(cls) -> str:
        """vision_agent"""
        return "vision_agent"

    async def execute(self, messages: Messages) -> Messages:
        """执行agent"""
        print(self.name())
        vision_message = messages.get(*self.roles)  # 提取需要的消息
        for tool in self.call_tools(messages):
            params = self.Params.parse_raw(tool.function.arguments)
            contents: list[Content] = [Content(type="text", value=params.desc)]
            contents.extend(Content(type="image", value=url) for url in params.urls)
            vision_message.user_message(contents)
            response = await client_create(vision_message, multi_modal=True)  # 将识别后的结果返回给message
            messages.tool_message(tool.id, response.choices[0].message.content or "")
            auto_tasks = AutoTaskList.parse_str(response.choices[0].message.content or "")
            if auto_tasks.tasks:
                messages.assistant_message(response.choices[0].message.content or "")
                self.finish()
        return messages


class FileAgent(BaseFunctionAgent):
    """机器人文件模块,可以帮助机器人解析文件"""

    roles: set[Role] = {Role.system}
    """引用哪个Role消息"""

    class Params(BaseModel):
        desc: str = Field(description="描述想要从文件中了解什么信息")
        urls: list[str] = Field(description="一个或多个文件url")

    @classmethod
    def name(cls) -> str:
        """file_agent"""
        return "file_agent"

    async def execute(self, messages: Messages) -> Messages:
        """执行agent"""
        print(self.name())
        images = []
        file_message = messages.get(*self.roles)  # 提取需要的消息

        async with AsyncClient() as client:
            for tool in self.call_tools(messages):
                params = self.Params.parse_raw(tool.function.arguments)
                for url in params.urls:
                    response = await client.get(url)
                    file_to_image = await File2Image(response.content, save_path=autogpt_dir)
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
    @classmethod
    def name(cls) -> str:
        """llm_agent"""
        return "llm_agent"

    async def execute(self, messages: Messages) -> Messages:
        if messages[-1].role == Role.assistant:
            return messages
        response = await client_create(messages, self.functions(), multi_modal=False)
        if response.choices[0].message.tool_calls:
            messages.add_tool(response.choices[0].message)
        else:
            messages.assistant_message(response.choices[0].message.content or "")
        return messages


class SummaryAgent(BaseAgent):
    """机器人聊天总结模块,可以帮助机器人总结对话内容"""

    max_chars: int = 24000
    """最大字符数"""

    @classmethod
    def name(cls) -> str:
        """summary_agent"""
        return "summary_agent"

    async def execute(self, messages: Messages) -> Messages:
        """执行agent"""
        message_chars = messages.char_length()
        print(self.name(), message_chars)
        if message_chars > self.max_chars:
            system_message = messages.get(Role.system)
            summary_message = messages.get(Role.user, Role.assistant)  # 提取需要的消息
            summary_message.user_message("针对之前的聊天内容进行总结,总结长度不超过2000字.")
            response = await client_create(summary_message, multi_modal=True)
            summary_text = response.choices[0].message.content or ""
            messages.clear()
            messages.extend(system_message)
            messages.assistant_message("# 历史聊天内容总结\n" + summary_text)
        return messages
