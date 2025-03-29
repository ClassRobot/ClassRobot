from typing import Annotated

from pydantic import BaseModel
from nonebot.params import Depends
from utils.tools import check_punctuation
from nonebot.adapters import Event as BaseEvent
from nonebot_plugin_alconna import MsgTarget, SupportScope, SupportAdapter

ignore_str = ["_", "-"]


class BaseSession(BaseModel):
    user_id: str
    platform: str
    platform_name: str
    channel_id: str | None
    "群ID或者子频道ID"
    guild_id: str | None = None

    @property
    def is_private(self) -> bool:
        return self.channel_id is None

    @property
    def is_group(self) -> bool:
        return not self.is_private

    @property
    def is_guild(self) -> bool:
        return self.guild_id is not None


class GroupSession(BaseSession):
    channel_id: str


class PrivateSession(BaseSession):
    ...


async def session(target: MsgTarget, event: BaseEvent) -> BaseSession | None:
    if target.scope and target.adapter:
        scope = SupportScope(target.scope)
        adapter = SupportAdapter(target.adapter)
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
    if session.is_group:
        return GroupSession.parse_obj(session)


GroupEventSession = Annotated[GroupSession, Depends(group_session)]


async def private_session(
    session: EventSession,
) -> PrivateSession | None:
    if session.is_private:
        return PrivateSession.parse_obj(session)


PrivateEventSession = Annotated[PrivateSession, Depends(private_session)]
