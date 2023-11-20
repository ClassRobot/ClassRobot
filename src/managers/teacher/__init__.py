from utils.models import User
from utils.typings import UserType
from nonebot_plugin_alconna import At
from utils.session import SessionPlatform
from nonebot.internal.matcher import Matcher
from utils.models.depends import get_user, create_user, set_teacher, remove_teacher

from .commands import add_teacher_cmd, remove_teacher_cmd


@add_teacher_cmd.handle()
async def _(
    matcher: Matcher,
    platform: SessionPlatform,
    name: str,
    phone: int,
    user_id: At | int,
    user: User,
):
    if isinstance(user_id, At):  # 如果是at添加教师，先查看用户是否存在，如果不存在则创建用户后添加为教师
        if (set_user := await get_user(platform.id, user_id.target)) is None:
            set_user = await create_user(platform.id, user_id.target, UserType.USER)
    elif (set_user := await get_user(user_id)) is None:  # 如果是输入用户id，当用户id不存在则告知用户
        await matcher.finish("用户不存在")

    match set_user.user_type:
        case UserType.TEACHER:
            await matcher.finish(f"用户[{set_user.id}]已经是教师")
        case UserType.STUDENT:
            await matcher.finish(f"用户[{set_user.id}]是学生，不能设置为教师")
        case UserType.ADMIN:
            await matcher.finish(f"用户[{set_user.id}]是管理员，不能设置为教师")
        case UserType.USER:
            await set_teacher(name, phone, user, set_user)
            await matcher.finish(f"成功将[{set_user.id}]设置为教师")


@remove_teacher_cmd.handle()
async def _(matcher: Matcher, platform: SessionPlatform, user_id: At | int):
    if set_user := (
        await get_user(user_id)
        if isinstance(user_id, int)
        else await get_user(platform.id, user_id.target)
    ):
        if set_user.user_type == UserType.TEACHER:
            await remove_teacher(set_user)
            await matcher.finish(f"成功将[{set_user.id}]移除教师")
        else:
            await matcher.finish(f"用户[{set_user.id}]不是教师")
    else:
        await matcher.finish("用户不存在")
