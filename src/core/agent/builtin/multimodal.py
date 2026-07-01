from nonebot import logger
from httpx import AsyncClient
from pydantic import Field, BaseModel
from src.platform.config import autogpt_dir
from src.core.llm import LLMTaskType, client_create
from src.core.skills import document_to_image_skill
from src.core.llm.message import Content, LLMRole, Messages

from ..base import BaseAgentConfig, BaseFunctionAgent


class VisionAgentConfig(BaseAgentConfig):
    """视觉理解 Agent 的运行配置。"""

    roles: tuple[LLMRole, ...] = (LLMRole.system,)


class FileAgentConfig(BaseAgentConfig):
    """文件理解 Agent 的运行配置。"""

    roles: tuple[LLMRole, ...] = (LLMRole.system,)


class VisionAgent(BaseFunctionAgent):
    """负责将图片内容交给多模态模型分析，并提取用户关心的信息。"""

    agent_name = "vision_agent"
    display_name = "视觉理解智能体"
    capabilities = ("vision", "image_understanding")
    config: VisionAgentConfig = Field(default_factory=VisionAgentConfig)
    """引用哪个 Role 消息。"""

    class Params(BaseModel):
        """描述图片识别工具需要的输入参数。"""

        desc: str = Field(description="描述想要从图片中了解什么信息")
        urls: list[str] = Field(description="一个或多个图片url")

    @property
    def roles(self) -> set[LLMRole]:
        """返回当前视觉 Agent 读取的消息角色范围。"""

        return set(self.config.roles)

    async def execute(self, messages: Messages) -> Messages:
        """处理视觉工具调用，并把识别结果写回消息列表。

        Args:
            messages: 当前会话的消息集合。

        Returns:
            Messages: 写入视觉识别结果后的消息集合。
        """
        logger.debug(self.name())
        vision_message = messages.get(*self.roles)
        for tool in self.call_tools(messages):
            params = self.Params.model_validate_json(tool.function.arguments)
            contents: list[Content] = [Content(type="text", value=params.desc)]
            contents.extend(Content(type="image", value=url) for url in params.urls)
            vision_message.user_message(contents)
            response = await client_create(
                vision_message,
                multi_modal=True,
                task_type=LLMTaskType.vision,
            )
            messages.tool_message(tool.id, response.choices[0].message.content or "")
        return messages


class FileAgent(BaseFunctionAgent):
    """负责将文档转为图片后交给多模态模型解析内容。"""

    agent_name = "file_agent"
    display_name = "文件理解智能体"
    capabilities = ("file_understanding", "document_to_image")
    config: FileAgentConfig = Field(default_factory=FileAgentConfig)
    """引用哪个 Role 消息。"""

    class Params(BaseModel):
        """描述文件解析工具需要的输入参数。"""

        desc: str = Field(description="描述想要从文件中了解什么信息")
        urls: list[str] = Field(description="一个或多个文件url")

    @property
    def roles(self) -> set[LLMRole]:
        """返回当前文件 Agent 读取的消息角色范围。"""

        return set(self.config.roles)

    async def execute(self, messages: Messages) -> Messages:
        """处理文件解析工具调用，并将结果写回消息列表。

        Args:
            messages: 当前会话的消息集合。

        Returns:
            Messages: 写入文件解析结果后的消息集合。
        """
        logger.debug(self.name())
        file_message = messages.get(*self.roles)

        async with AsyncClient() as client:
            for tool in self.call_tools(messages):
                params = self.Params.model_validate_json(tool.function.arguments)
                images: list[str] = []
                for url in params.urls:
                    response = await client.get(url)
                    # Office/PDF 先统一转图片，再复用同一条多模态理解链路。
                    file_to_image = await document_to_image_skill.convert(response.content, save_path=autogpt_dir)
                    images.extend(file_to_image.images)
                if images:
                    contents: list[Content] = [Content(type="text", value=params.desc)]
                    contents.extend(Content(type="image", value=url) for url in images)
                    file_message.user_message(contents)
                    response = await client_create(
                        file_message,
                        multi_modal=True,
                        task_type=LLMTaskType.vision,
                    )
                    messages.tool_message(tool.id, response.choices[0].message.content or "")
                else:
                    messages.tool_message(
                        tool.id,
                        "解析失败:\n该文件过大或者文件类型不正确，只能识别 ppt、doc、pdf 类型的文件",
                    )
        return messages
