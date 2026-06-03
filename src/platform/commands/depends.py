from __future__ import annotations

from typing import Annotated

from nonebot.adapters import Event
from nonebot.params import Depends
from src.platform.session import EventSession
from src.platform.session.depends import UserOrCreatedDepends

from .context import CommandExecutionContext, normalize_user_roles


async def build_user_command_context(
    user: UserOrCreatedDepends,
    platform: EventSession,
    event: Event,
) -> CommandExecutionContext:
    """为用户直发命令构建统一 service 执行上下文。

    这里依赖 NoneBot 原生注入解析用户和会话，避免命令轻量 schema
    模块在导入期触碰用户模型或 ORM 配置。
    """

    return CommandExecutionContext(
        user_id=user.id,
        roles=normalize_user_roles(set(user.roles)),
        platform=platform.platform,
        channel_id=platform.channel_id,
        guild_id=platform.guild_id,
        invoker="user_command",
        extra={
            "platform_name": platform.platform_name,
            "message_id": str(getattr(event, "message_id", "") or ""),
        },
    )


CommandUserContextDepends = Annotated[CommandExecutionContext, Depends(build_user_command_context)]
