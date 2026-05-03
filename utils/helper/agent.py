from nonebot import logger
from pydantic import Field, BaseModel
from utils.llm.message import Messages
from utils.llm.agents import BaseFunctionAgent

from .config import helper_menu
from .schema import Helpers


class HelperAgent(BaseFunctionAgent):
    """帮助文档模块,详细介绍命令的使用方式,辅助机器人更好的里面命令来生成task"""

    helpers: Helpers = Field(default_factory=lambda: helper_menu)
    """当前 agent 可读取的帮助目录；需要鉴权时应传入已按用户过滤的集合。"""

    class Params(BaseModel):
        """描述params使用的配置或数据结构。"""

        commands: list[str] = Field(description="一个或多个命令的帮助文档")

    @classmethod
    def name(cls) -> str:
        """返回帮助工具智能体的注册名称。"""
        return "helper_agent"

    async def execute(self, messages: Messages) -> Messages:
        """执行当前逻辑。

        参数:
            messages (Messages): 消息列表。

        返回:
            Messages: 返回处理结果。
        """
        logger.debug(self.name())
        for tool in self.call_tools(messages):
            params = self.Params.parse_raw(tool.function.arguments)
            helpers: list[str] = []
            for cmd in params.commands:
                if helper := self.helpers.get_helper(cmd):
                    helpers.append(helper.to_string())
            messages.tool_message(tool.id, "\n".join(helpers))
        return messages
