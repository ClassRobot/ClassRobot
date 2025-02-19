from typing import Annotated

from utils import Emoji
from nonebot.params import Depends
from nonebot.matcher import Matcher
from utils.models.annotated import StudentDepends

from .manage import AddLeave


async def add_leave_depends(matcher: Matcher, student: StudentDepends) -> AddLeave:
    if student:
        return matcher.state.setdefault("_add_leave", AddLeave(student))
    else:
        await matcher.finish(Emoji.error + "您还未绑定学生信息！！")


AddLeaveDepends = Annotated[AddLeave, Depends(add_leave_depends)]
