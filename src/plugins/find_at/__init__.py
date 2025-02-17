from utils import Emoji
from utils.models import Bind
from utils.config import template_dir
from nonebot.adapters import Event, qq
from utils.session import EventSession
from nonebot_plugin_htmlrender import template_to_pic
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher

from .util import get_display_columns
from .commands import at_cmd, find_student_cmd
from .depends import FindStudents, UserStudents


@find_student_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    find_students: FindStudents,
    students: UserStudents,
    items: list[str],
):
    if not students:
        await matcher.finish(Emoji.error + "您没有可以查找的学生")
    elif find_students.empty:
        await matcher.finish(Emoji.error + "没有找到符合条件的学生")

    columns = get_display_columns(items)
    # 显示指定几个列,nan替换成空字符串
    find_students = find_students[columns].fillna("无").astype(str)
    await matcher.finish(
        UniMessage.image(
            raw=await template_to_pic(
                str(template_dir),
                "find.html",
                {
                    "data": find_students.to_dict(orient="records"),
                },
            )
        )
    )


@at_cmd.handle()
async def _(
    event: Event,
    session: EventSession,
    matcher: AlconnaMatcher,
    find_students: FindStudents,
):
    if isinstance(event, qq.Event):
        await matcher.finish(Emoji.error + "本功能暂不支持官方QQ机器人")
    if find_students.empty:
        await matcher.finish(Emoji.error + "没有找到符合条件的学生")

    at_user = UniMessage()

    for user_id in find_students.user_id:
        if user := await Bind.filter(
            platform_id=session.platform, user_id=user_id
        ).first():
            at_user += UniMessage.at(user.account_id)
    if at_user:
        await matcher.finish(at_user)
