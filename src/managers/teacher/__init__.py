from utils.models import User
from utils.typings import UserType
from nonebot_plugin_alconna import At
from sqlalchemy.exc import IntegrityError
from utils.params import UserIdOrAtParams
from utils.session import SessionPlatform
from nonebot.internal.matcher import Matcher
from utils.params.notes import ValidateNameNotNumeric
from utils.models.depends import get_user, get_teacher, create_teacher, delete_teacher

from .commands import del_teacher_cmd, become_teacher_cmd


@del_teacher_cmd.handle()
async def _(matcher: Matcher, platform: SessionPlatform, user_id: At | int):
    if set_user := (
        await get_user(user_id)
        if isinstance(user_id, int)
        else await get_user(platform.id, user_id.target)
    ):
        try:
            if await delete_teacher(set_user):
                await matcher.finish(f"成功将[{set_user.id}]移除教师")
            else:
                await matcher.finish(f"用户[{set_user.id}]不是教师")
        except IntegrityError:
            await matcher.finish(f"教师还存在班级，无法删除！")
    else:
        await matcher.finish("用户不存在或者还不是用户")


@become_teacher_cmd.handle()
async def _(
    phone: int,
    user: User,
    matcher: Matcher,
    name: ValidateNameNotNumeric,
):
    if teacher := await get_teacher(user):
        await matcher.finish(f"您已经是教师了, 您的教师id为[{teacher.id}]")
    teacher = await create_teacher(name, phone, user=user, creator=user)
    await matcher.finish(f"已将您设置为教师, 您的教师id为[{teacher.id}]")
