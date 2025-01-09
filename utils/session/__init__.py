from typing import Annotated
from nonebot.params import Depends
from nonebot_plugin_session import (
    EventSession as BaseEventSession,
    Session as BaseSession,
    SessionLevel,
)


class PrivateSession(BaseSession):
    @property
    def user_id(self) -> str:
        return self.id1 or ""

    def is_private(self) -> bool:
        return self.level == SessionLevel.PRIVATE and self.id1 is not None

    def is_group(self) -> bool:
        return self.level == SessionLevel.GROUP and self.id2 is not None

    def is_guild(self) -> bool:
        return self.id3 is not None


class GroupSession(PrivateSession):
    @property
    def channel_id(self) -> str:
        """群ID或子频道ID"""
        if self.id2:
            return self.id2
        raise ValueError("GroupSession id2 is None")

    @property
    def guild_id(self) -> str | None:
        """通常频道ID"""
        return self.id3

    @property
    def group_params(self) -> dict:
        return {
            "platform_id": self.platform,
            "channel_id": self.channel_id,
            "guild_id": self.guild_id,
        }


class Session(GroupSession):
    @property
    def group_id(self) -> str | None:
        return self.id2


async def group_session(session: BaseEventSession) -> GroupSession | None:
    if session.level == SessionLevel.GROUP and session.id2:
        return GroupSession.parse_obj(session)


GroupEventSession = Annotated[GroupSession, Depends(group_session)]


async def private_session(session: BaseEventSession) -> PrivateSession | None:
    if session.level == SessionLevel.PRIVATE and session.id1:
        return PrivateSession.parse_obj(session)


PrivateEventSession = Annotated[PrivateSession, Depends(private_session)]


async def session(session: BaseEventSession) -> Session | None:
    if session.id1:
        return Session.parse_obj(session)


EventSession = Annotated[Session, Depends(session)]
