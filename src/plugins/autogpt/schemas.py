from typing import Literal
from datetime import datetime

from utils.llm.schema import Content
from pydantic import Field, BaseModel
from nonebot_plugin_alconna import UniMessage
from utils.llm.util import uni_message_to_contents


class Param(BaseModel):
    type: Literal["text", "image"]
    separate: bool = False
    "命令和参数是否需要分开发送,例如`帮助`命令和`查询班级`参数需要分两次发送时候为True"
    value: str
    "如果是image则为url"


class AutoTask(BaseModel):
    "AI帮助用户自动执行任务"

    command: str
    "用户的话语中可能想要执行的命令(重点:该命令必须是机器人所具备的命令)"
    params: list[Param] = []
    "命令的参数"


class AutoTaskList(BaseModel):
    "机器人回复内容，自动任务列表"

    reply: str | None = None
    tasks: list[AutoTask] = []
    "用户的话语中可能想要执行的命令(重点:该命令必须是命令列表中的命令)"
    need_confirm: bool = False
    "当不确定用户意图的情况下设置为`True`,然后询问用户确认。"
    is_violation: bool = False
    "和用户在聊天过程中发现违规行为时设置为`True`。"


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
