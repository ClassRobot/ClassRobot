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

    tasks: list[AutoTask] = []
    "自动任务列表，如果存在的话，回复用户内容后会开始执行tasks中的任务"
    need_confirm: bool = False
    "`True`表示必须要询问用户是否要执行，但机器人如果非常确定用户的意图则可以不需要用户确认"
    reply: str | None = None
    "回复给用户的消息，如果`tasks`里面有任务的话则告知用户机器人接下来会帮助用户做什么，如果`need_confirm`为`True`则必须要询问用户是否要执行，具体情况由机器人自己去分析用户意图。"
    is_violation: bool = False
    "结合历史聊天内容判断用户是否在发送一些无意义、重复、反动、色情、暴力等不良信息，如果是则不做回复"


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
