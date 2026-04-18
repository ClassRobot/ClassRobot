import json
from typing import Literal
from datetime import datetime

from pydantic import Field, BaseModel
from utils.llm.util import json_loads


class Param(BaseModel):
    """命令参数"""

    type: Literal["text", "image"]
    separate: bool = Field(default=False, description="命令和参数是否需要分开发送,例如`帮助`命令和`查询班级`参数需要分两次发送时候为True")
    value: str = Field(description="如果是image则为url")


class AutoTask(BaseModel):
    "AI帮助用户自动执行任务"

    command: str = Field(description="命令名称")
    "用户的话语中可能想要执行的命令(重点:该命令必须是机器人所具备的命令)"
    params: list[Param] = Field(description="命令参数")
    "命令的参数"


class AutoTaskList(BaseModel):
    "机器人回复内容，自动任务列表"

    reply: str | None = Field(default=None, description="机器人回复内容")
    create_at: datetime = Field(default_factory=datetime.now)
    tasks: list[AutoTask] = Field(default=[], description="自动任务列表")
    "用户的话语中可能想要执行的命令(重点:该命令必须是命令列表中的命令)"
    need_confirm: bool = Field(default=False, description="用户意图不明确的情况下询问用户确认")
    "当不确定用户意图的情况下设置为`True`,然后询问用户确认。"
    is_violation: bool = Field(default=False, description="用户发送的消息包含违规内容")
    "和用户在聊天过程中发现违规行为时设置为`True`。"

    @classmethod
    def parse_str(cls, text: str) -> "AutoTaskList":
        """解析文本

        参数:
            text (str): 文本内容。

        返回:
            'AutoTaskList': 返回处理结果。
        """
        contents = text.split("<hr/>")
        task_data = contents[-1].strip()
        try:
            data = json_loads(task_data)
            if isinstance(data, list):
                data = data[0]
            auto_tasks = cls.parse_obj(data)
            contents = contents[:-1]
        except json.JSONDecodeError:
            auto_tasks = cls()

        auto_tasks.reply = "<hr/>".join(contents).strip()
        if auto_tasks.is_violation:
            auto_tasks.reply = "用户发送的消息包含违规内容，已被屏蔽！"

        # 更新最后一条消息
        return auto_tasks
