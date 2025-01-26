from typing import Literal
from datetime import datetime

from pydantic import Field, BaseModel
from nonebot_plugin_alconna import Text, Image, UniMessage


class Param(BaseModel):
    type: Literal["text", "image"]
    separate: bool = False
    "命令是否需要和参数分两次发送，假设`/search`命令的某个参数需要和命令需要分开发送时`separate`为`True`时自动化程序会将`/search`和`参数`分两次执行"
    value: str
    "参数值，当如果是image则为图片的url"


class AutoTask(BaseModel):
    "AI帮助用户自动执行任务"

    command: str
    "用户的话语中可能想要执行的命令"
    params: list[Param] = []
    "命令的参数"
    help: bool = False
    "对于命令的作用不是非常明确，或者命令的参数不是很清楚时，可以设置为True，机器人会查询命令的详细帮助"


class AutoTaskList(BaseModel):
    "机器人回复内容，自动任务列表"

    tasks: list[AutoTask] = []
    "自动任务列表，如果存在的话，回复用户内容后会开始执行tasks中的任务"
    need_confirm: bool = True
    "True表示必须要询问用户是否要执行，但机器人如果非常确定用户的意图则可以不需要用户确认"
    reply: str | None = None
    "回复给用户的消息，如果`tasks`里面有任务的话则告知用户机器人接下来会帮助用户做什么，如果`need_confirm`为`True`则必须要询问用户是否要执行，为`False`时`reply`可以为空，具体情况由机器人自己去分析用户意图。"
    is_violation: bool = False
    "结合历史聊天内容判断用户是否在发送一些无意义、重复、反动、色情、暴力等不良信息，如果是则不做回复"


class ChatMessage(BaseModel):
    "用户的聊天消息"

    role: Literal["user", "help"] = "user"
    "消息角色, user: 用户, help: 帮助文档"
    user_id: int | None = None
    "用户ID"
    message: list[Param] = []
    "消息内容"
    create_at: datetime = Field(default_factory=datetime.now)
    "消息创建时间"

    def extend(self, message: UniMessage | str):
        if isinstance(message, str):
            self.message.append(Param(type="text", value=message))
        else:
            for msg in message:
                if isinstance(msg, Text):
                    self.message.append(Param(type="text", value=msg.text))
                elif isinstance(msg, Image) and msg.url:
                    self.message.append(Param(type="image", value=msg.url))
        return self

    def to_string(self):
        return self.json(ensure_ascii=False)

    def __str__(self) -> str:
        return self.to_string()
