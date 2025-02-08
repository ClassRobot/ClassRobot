from utils import Emoji
from utils.models import Bind
from utils.session import EventSession
from nonebot_plugin_htmlrender import md_to_pic
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher

from .commands import at_cmd, find_cmd
from .depends import FindStudents, UserStudents


@find_cmd.handle()
async def _(
    matcher: AlconnaMatcher, find_students: FindStudents, students: UserStudents
):
    if not students:
        await matcher.finish(Emoji.error + "您没有可以查找的学生")
    elif find_students.empty:
        await matcher.finish(Emoji.error + "没有找到符合条件的学生")

    html = find_students.to_markdown(index=False)
    await matcher.finish(UniMessage.image(raw=await md_to_pic(md=html, width=1200)))


@at_cmd.handle()
async def _(
    matcher: AlconnaMatcher, find_students: FindStudents, session: EventSession
):
    if find_students.empty:
        await matcher.finish(Emoji.error + "没有找到符合条件的学生")

    at_user = UniMessage()

    for user_id in find_students.user_id:
        if user := await Bind.filter(
            platform_id=session.platform, user_id=user_id
        ).first():
            at_user += UniMessage.at(user.account_id)

    await matcher.finish(at_user)
