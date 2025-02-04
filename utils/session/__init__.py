from typing import Annotated

from pydantic import BaseModel
from nonebot.params import Depends
from nonebot.adapters import Event as BaseEvent
from nonebot_plugin_alconna import MsgTarget, SupportScope, SupportAdapter


class BaseSession(BaseModel):
    user_id: str
    platform: str
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

    @property
    def group_params(self) -> dict:
        return {
            "platform_id": self.platform,
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
        }


class GroupSession(BaseSession):
    channel_id: str


class PrivateSession(BaseSession): ...


async def session(target: MsgTarget, event: BaseEvent) -> BaseSession | None:
    if target.scope and target.adapter:
        scope = SupportScope(target.scope)
        adapter = SupportAdapter(target.adapter)
        platform = ".".join((adapter.name, scope.name))
        return BaseSession(
            user_id=event.get_user_id(),
            platform=platform,
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
