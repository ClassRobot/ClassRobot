from typing import Annotated

from src.shared import Emoji
from nonebot.params import Depends
from nonebot.matcher import Matcher
from src.models.depends import UserDepends, StudentDepends

from .manage import AddLeave, QueryLeave


async def add_leave_depends(matcher: Matcher, student: StudentDepends) -> AddLeave:
    """构建添加请假依赖。"""
    if student:
        return matcher.state.setdefault("_add_leave", AddLeave(student))
    else:
        await matcher.finish(Emoji.error + "您还未绑定学生信息，请假是学生相关功能！！")


AddLeaveDepends = Annotated[AddLeave, Depends(dependency=add_leave_depends)]


async def query_leave_depends(matcher: Matcher, user: UserDepends):
    """构建查询请假依赖。"""
    if user is None:
        await matcher.finish(Emoji.error + "没有与您相关请假信息！")
    return matcher.state.setdefault("_query_leave", QueryLeave(user))


QueryLeaveDepends = Annotated[QueryLeave, Depends(dependency=query_leave_depends)]
