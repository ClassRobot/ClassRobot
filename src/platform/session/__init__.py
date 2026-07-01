from typing import Annotated

from pydantic import BaseModel
from nonebot.adapters import Bot
from nonebot.params import Depends
from src.shared.tools import check_punctuation
from nonebot.adapters import Event as BaseEvent
from nonebot_plugin_alconna import MsgTarget, SupportScope, SupportAdapter

ignore_str = ["_", "-"]


class BaseSession(BaseModel):
    """描述一次消息会话的基础标识信息，用于区分私聊、群聊和频道场景。"""

    user_id: str
    platform: str
    platform_name: str
    channel_id: str | None = None
    "群ID或者子频道ID"
    guild_id: str | None = None

    @property
    def is_private(self) -> bool:
        """判断是否为私聊。"""
        return self.channel_id is None

    @property
    def is_group(self) -> bool:
        """检查群组。"""
        return not self.is_private

    @property
    def is_guild(self) -> bool:
        """检查频道。"""
        return self.guild_id is not None


class GroupSession(BaseSession):
    """表示群聊或频道场景下的会话信息。"""

    channel_id: str


class PrivateSession(BaseSession):
    """表示私聊场景下的会话信息。"""

    ...


async def session(bot: Bot, event: BaseEvent) -> BaseSession | None:
    """根据消息目标与事件对象构建统一的会话信息。

    Args:
        bot: 当前事件所属机器人。
        event: 触发当前处理流程的事件对象。

    Returns:
        BaseSession | None: 构建出的会话对象；无法识别时返回 `None`。
    """

    from src.platform.session.resolvers import resolve_session_from_event

    return resolve_session_from_event(bot, event)


async def session_from_target(target: MsgTarget, event: BaseEvent) -> BaseSession | None:
    """根据 Alconna 目标构建统一会话。

    该函数保留给已经拿到 `MsgTarget` 的调用方复用；普通 NoneBot 依赖
    使用 :func:`session`，从而在 wxclaw 尚未被 Alconna 支持时也可以
    通过事件字段兜底生成会话。
    """

    if target.scope and target.adapter:
        scope = SupportScope(target.scope)
        adapter = SupportAdapter(target.adapter)
        # User bindings and storage keys rely on a stable `adapter.scope` identity,
        # so reject punctuation here before composing the platform string.
        if check_punctuation(adapter.name, ignore_str) or check_punctuation(scope.name, ignore_str):
            raise ValueError(f"platform '{adapter.name}' or scope '{scope.name}' contains illegal characters")
        elif target.platform and any(check_punctuation(i, ignore_str) for i in target.platform):
            raise ValueError(f"platform_name '{target.platform}' contains illegal characters")

        platform = ".".join((adapter.name, scope.name))
        platform_name = ".".join(target.platform or [])

        return BaseSession(
            user_id=event.get_user_id(),
            platform=platform,
            platform_name=platform_name,
            guild_id=target.parent_id,
            channel_id=target.id if not target.private else None,
        )


EventSession = Annotated[BaseSession, Depends(session)]


async def group_session(session: EventSession) -> GroupSession | None:
    """在群聊场景下返回群组会话对象。

    参数:
        session (EventSession): 通用会话对象。

    返回:
        GroupSession | None: 当前会话是群聊时返回群组会话对象。
    """
    if session.is_group:
        return GroupSession.model_validate(session)


GroupEventSession = Annotated[GroupSession, Depends(group_session)]


async def private_session(
    session: EventSession,
) -> PrivateSession | None:
    """在私聊场景下返回私聊会话对象。

    参数:
        session (EventSession): 通用会话对象。

    返回:
        PrivateSession | None: 当前会话是私聊时返回私聊会话对象。
    """
    if session.is_private:
        return PrivateSession.model_validate(session)


PrivateEventSession = Annotated[PrivateSession, Depends(private_session)]
