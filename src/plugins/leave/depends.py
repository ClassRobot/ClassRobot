from typing import Annotated

from utils import Emoji
from nonebot.params import Depends
from nonebot.matcher import Matcher
from utils.models.depends import UserDepends, StudentDepends

from .manage import AddLeave, QueryLeave


async def add_leave_depends(matcher: Matcher, student: StudentDepends) -> AddLeave:
    if student:
        return matcher.state.setdefault("_add_leave", AddLeave(student))
    else:
        await matcher.finish(Emoji.error + "您还未绑定学生信息！！")


AddLeaveDepends = Annotated[AddLeave, Depends(dependency=add_leave_depends)]


async def query_leave_depends(matcher: Matcher, user: UserDepends):
    if user is None:
        await matcher.finish(Emoji.error + "没有与您相关信息！")
    return matcher.state.setdefault("_query_leave", QueryLeave(user))


QueryLeaveDepends = Annotated[QueryLeave, Depends(dependency=query_leave_depends)]
