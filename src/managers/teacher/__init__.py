from utils.models import User
from utils.typings import UserType
from nonebot_plugin_alconna import At
from sqlalchemy.exc import IntegrityError
from utils.params import UserIdOrAtParams
from utils.session import SessionPlatform
from nonebot.internal.matcher import Matcher
from utils.models.depends import get_user, get_teacher, create_teacher, delete_teacher

from .commands import add_teacher_cmd, del_teacher_cmd


@add_teacher_cmd.handle()
async def _(
    matcher: Matcher,
    name: str,
    phone: int,
    user: User,
    set_user: User = UserIdOrAtParams(True),
):
    match set_user.user_type:
        case UserType.TEACHER | UserType.ADMIN:  # 查看是否是管理员或教师
            if (
                set_user.user_type == UserType.ADMIN and await get_teacher(set_user)
            ) or True:  # 如果是管理员则查询数据库查看是否有教师身份
                await matcher.finish(f"用户[{set_user.id}]已经是教师")
        case UserType.STUDENT:
            await matcher.finish(f"用户[{set_user.id}]是学生，不能设置为教师")
    try:
        await create_teacher(name, phone, user=set_user, creator=user)
        await matcher.finish(f"成功将[{set_user.id}]设置为教师")
    except IntegrityError:
        await matcher.finish(f"教师联系方式可能已存在")


@del_teacher_cmd.handle()
async def _(matcher: Matcher, platform: SessionPlatform, user_id: At | int):
    if set_user := (
        await get_user(user_id)
        if isinstance(user_id, int)
        else await get_user(platform.id, user_id.target)
    ):
        if set_user.user_type == UserType.TEACHER:
            await delete_teacher(set_user)
            await matcher.finish(f"成功将[{set_user.id}]移除教师")
        else:
            await matcher.finish(f"用户[{set_user.id}]不是教师")
    else:
        await matcher.finish("用户不存在或者还不是用户")
