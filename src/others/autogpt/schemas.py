from typing import Literal

from pydantic import BaseModel


class Param(BaseModel):
    type: Literal["text", "image"]
    value: str
    "参数值，当如果是image则为图片的url"


class AutoTask(BaseModel):
    "AI帮助用户自动执行任务"

    command: str
    "触发的命令"
    params: list[Param] = []
    "命令的参数"
    query_command_help: bool = False
    "机器人如果不确定命令的使用方式是否正确时该参数为True会查询命令详细帮助"


class AutoTaskList(BaseModel):
    "自动任务列表"

    tasks: list[AutoTask] = []
    "自动任务列表，如果存在的话，回复用户内容后会开始执行tasks中的任务"
    need_confirm: bool = True
    "True表示必须要询问用户是否要执行，但机器人如果非常确定用户的意图则可以不需要用户确认"
    reply: str | None = None
    "回复给用户的消息，如果tasks里面有任务的话则告知用户机器人接下来会帮助用户做什么，如果need_confirm为True则必须要询问用户是否要执行，为False时reply可以为空，具体情况由机器人自己去分析。"
