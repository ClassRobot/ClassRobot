from typing import Annotated

from nonebot.params import Depends
from nonebot.matcher import Matcher
from utils.models.annotated import UserOrCreatedDepends

from .util import NoticeSession


async def get_notice_session(
    matcher: Matcher, user: UserOrCreatedDepends
) -> NoticeSession:
    notice_session = matcher.state.setdefault("_notice_session", NoticeSession(user))
    return notice_session


NoticeSessionDepends = Annotated[NoticeSession, Depends(get_notice_session)]
