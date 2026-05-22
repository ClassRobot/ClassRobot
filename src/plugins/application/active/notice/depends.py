from typing import Annotated

from nonebot.params import Depends
from nonebot.matcher import Matcher
from src.models.depends import UserOrCreatedDepends

from .util import NoticeSession
from .manage import QueryNotice, DeleteNotice


async def get_notice_session(matcher: Matcher, user: UserOrCreatedDepends) -> NoticeSession:
    """获取通知会话。"""
    notice_session = matcher.state.setdefault("_notice_session", NoticeSession(user))
    return notice_session


NoticeSessionDepends = Annotated[NoticeSession, Depends(get_notice_session)]


async def query_notice_depends(matcher: Matcher, user: UserOrCreatedDepends) -> QueryNotice:
    """构建查询通知依赖。"""
    return matcher.state.setdefault("_query_notice", QueryNotice(user))


QueryNoticeDepends = Annotated[QueryNotice, Depends(dependency=query_notice_depends)]


async def delete_notice_depends(matcher: Matcher, user: UserOrCreatedDepends) -> DeleteNotice:
    """构建删除通知依赖。"""
    return matcher.state.setdefault("_delete_notice", DeleteNotice(user))


DeleteNoticeDepends = Annotated[DeleteNotice, Depends(dependency=delete_notice_depends)]
