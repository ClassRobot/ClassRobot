from typing import Literal
from datetime import datetime

from pydantic import Field, BaseModel
from utils.llm.message import Content
from nonebot_plugin_alconna import UniMessage
from utils.llm.util import uni_message_to_contents


class ChatMessage(BaseModel):
    "用户的聊天消息"

    role: Literal["user", "help"] = "user"
    "消息角色, user: 用户, help: 帮助文档"
    user_id: int | None = None
    "用户ID"
    message: list[Content] = []
    "消息内容"
    create_at: datetime = Field(default_factory=datetime.now)
    "消息创建时间"

    def extend(self, message: UniMessage | str):
        self.message.extend(uni_message_to_contents(message))
        return self.message
