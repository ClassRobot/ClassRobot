from typing import Literal
from datetime import datetime

from pydantic import Field, BaseModel
from utils.llm.message import Content
from nonebot_plugin_alconna import UniMessage
from utils.llm.util import uni_message_to_contents
from utils.schemas.auto_task import Param as Param  # noqa
from utils.schemas.auto_task import AutoTask as AutoTask  # noqa
from utils.schemas.auto_task import AutoTaskList as AutoTaskList  # noqa


class IntentRoute(BaseModel):
    """AutoGPT 对当前消息的入口路由判断。"""

    intent: Literal["chat", "knowledge", "command", "complex_task", "vision_file", "violation"] = "chat"
    """当前消息的主要意图类型。"""
    reply: str | None = None
    """可以直接回复用户时填写。"""
    requires_rag: bool = False
    """是否需要检索知识库。"""
    requires_command: bool = False
    """是否需要规划并调用项目命令。"""
    need_confirm: bool = False
    """是否需要用户补充信息或确认。"""
    reason: str = ""
    """简短说明路由原因，供日志和调试使用。"""


class AgentPlan(BaseModel):
    """AutoGPT 对当前任务的显式执行计划。"""

    goal: str = ""
    """用户最终想完成的目标。"""
    facts: list[str] = []
    """已经确认的事实。"""
    missing_info: list[str] = []
    """执行前仍缺少的信息。"""
    risk_level: Literal["low", "medium", "high"] = "low"
    """计划风险等级。"""
    requires_rag: bool = False
    """是否需要知识检索。"""
    requires_command: bool = False
    """是否需要调用项目命令。"""
    should_execute: bool = False
    """当前是否可以直接执行命令。"""
    candidate_commands: list[str] = []
    """可能要调用的项目命令名称。"""
    steps: list[str] = []
    """面向系统的执行步骤。"""
    confirmation_question: str | None = None
    """需要向用户确认时的问题。"""
    reason: str = ""
    """简短说明计划理由。"""


class CommandObservation(BaseModel):
    """AutoGPT 命令投递后的结构化观察记录。"""

    trace_id: str = ""
    """本轮 AutoGPT 请求的追踪 ID。"""
    command: str
    """被投递的项目命令名称。"""
    params: list[Param] = Field(default_factory=list)
    """本次随命令一起投递的参数。"""
    dispatch_type: Literal["command", "separate_param", "missing_command"] = "command"
    """投递类型：主命令、分离参数或缺失命令。"""
    success: bool = True
    """是否成功投递到 NoneBot 事件系统。"""
    message: str = ""
    """投递结果说明。"""
    created_at: datetime = Field(default_factory=datetime.now)
    """观察记录创建时间。"""


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
        """扩展当前集合。

        参数:
            message (UniMessage | str): 消息对象。
        """
        self.message.extend(uni_message_to_contents(message))
        return self.message
