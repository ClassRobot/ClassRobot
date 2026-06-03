from __future__ import annotations

from typing import Any, Literal

from nonebot import logger
from src.core.auth import UserRole
from pydantic import Field, BaseModel

CommandInvoker = Literal["user_command", "agent_workflow", "system"]


class CommandParams(dict[str, Any]):
    """命令 service 的轻量参数读取对象。

    用户命令和 Agent 调用会保留不同来源的参数键：中文 label 更适合
    Agent 工具 schema，Alconna source name 更贴近用户 matcher 解析结果。
    这个对象让 service 只写一次读取逻辑，不再到处复制 ``_read_param``。
    """

    def get_value(self, label: str, source_name: str | None = None, default: Any = "") -> Any:
        """按中文 label、source name 的顺序读取参数值。"""

        if label in self:
            return self[label]
        if source_name and source_name in self:
            return self[source_name]
        return default

    def require_value(self, label: str, source_name: str | None = None) -> Any:
        """读取必填参数；缺失或空字符串时抛出 ``KeyError``。"""

        value = self.get_value(label, source_name, None)
        if value is None or value == "":
            raise KeyError(label)
        return value


def normalize_user_roles(
    roles: set[UserRole | str] | list[UserRole | str] | tuple[UserRole | str, ...] | None,
) -> set[UserRole]:
    """把入口侧角色值转换成命令执行上下文使用的角色枚举。"""

    normalized: set[UserRole] = set()
    for role in roles or []:
        if isinstance(role, UserRole):
            normalized.add(role)
            continue
        try:
            normalized.add(UserRole(role))
        except ValueError:
            logger.warning(f'Ignored unknown user role "{role}" while building command execution context')
    return normalized


class CommandExecutionContext(BaseModel):
    """描述一次与具体入口解耦的命令调用上下文。

    该对象只保存稳定运行时事实。平台事件、消息段等适配器对象应停留在
    adapter 层，避免 service 和 policy 必须依赖 NoneBot 才能测试。
    """

    user_id: int | None = None
    """已解析出的项目用户 ID。"""
    roles: set[UserRole] = Field(default_factory=set)
    """调用发生时用户拥有的静态角色集合。"""
    platform: str | None = None
    """适配器或平台标识，例如 ``qq`` 或 ``onebot11``。"""
    channel_id: str | None = None
    """频道、群组或会话 ID。"""
    guild_id: str | None = None
    """区分频道和服务器的适配器使用的 guild ID。"""
    trace_id: str = ""
    """命令、Agent 工作流和审计日志共享的追踪 ID。"""
    invoker: CommandInvoker = "user_command"
    """调用来源：用户显式命令、Agent 工作流或系统任务。"""
    silent: bool = False
    """是否由适配层抑制用户可见输出。"""
    session_id: str | None = None
    """用于上下文回写的可选会话 ID。"""
    extra: dict[str, Any] = Field(default_factory=dict)
    """适配器扩展字段；不要在这里放领域业务数据。"""
