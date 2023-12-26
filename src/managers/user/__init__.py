from utils.models import User
from utils.formant import line
from utils.params import UserId
from nonebot.typing import T_State
from nonebot.params import ArgPlainText
from utils.session import SessionPlatform
from nonebot.internal.matcher import Matcher
from nonebot_plugin_orm import async_scoped_session
from utils.typings import UserType, UserTypeChinese
from utils.models.depends import (
    get_user,
    create_user,
    get_student,
    get_teacher,
    rebind_user,
    add_user_bind,
    update_user_type,
)

from .bind_token import BindUser, get_bind_token
from .commands import (
    bind_user_cmd,
    show_user_cmd,
    bind_token_cmd,
    create_user_cmd,
    become_admin_cmd,
)

admin_codes = ["test"]


# --------------------------------- 创建用户 ---------------------------------
@create_user_cmd.handle()
async def _(
    matcher: Matcher,
    session: SessionPlatform,
    user_id: UserId,
):
    if await get_user(session.id, user_id):
        await matcher.finish(f"您已经是用户了, 不要重复创建哦")
    elif user := await create_user(session.id, user_id, UserType.USER):
        await matcher.finish(f"已将您设置为用户, 您的用户id为[{user.id}]")


# --------------------------------- 用户信息 ---------------------------------
@show_user_cmd.handle()
async def _(
    matcher: Matcher,
    user: User,
):
    reply = (
        f"您的用户信息\n{line}\n● 用户id:\t{user.id}\n● 身份:\t{UserTypeChinese[user.user_type]}"
    )

    match user.user_type:
        case UserType.ADMIN | UserType.TEACHER:
            if teacher := await get_teacher(user):
                reply += f"\n{line}\n● 教师id:\t{teacher.id}\n● 昵称:\t{teacher.name}\n● 电话:\t{teacher.phone}"
        case UserType.ADMIN | UserType.STUDENT:
            if student := await get_student(user):
                reply += f"\n{line}\n● 学生id:\t{student.id}\n● 昵称:\t{student.name}"
    await matcher.finish(reply)


# --------------------------------- 成为管理员 ---------------------------------
@become_admin_cmd.handle()
async def _(matcher: Matcher, user: User, code: str, session_orm: async_scoped_session):
    if code in admin_codes:
        await update_user_type(user, UserType.ADMIN, session_orm)
        await session_orm.commit()
        await become_admin_cmd.finish(f"成功将您设置为管理员")
    await matcher.finish("管理员邀请码错误")


# --------------------------------- 绑定指定平台 ---------------------------------
@bind_user_cmd.handle()
async def _(matcher: Matcher, user: User):
    token = get_bind_token(user.id)
    await matcher.finish(f"请复制以下内容发送到您需要绑定的平台的本机器人(5分钟内有效):\nbind_token={token}")


# --------------------------------- 绑定的token ---------------------------------
@bind_token_cmd.handle()
async def _(
    state: T_State,
    matcher: Matcher,
    user_id: UserId,
    session: SessionPlatform,
    bind_user: User = BindUser,
):
    # 查看该平台是否已经绑定了某个用户
    if old_user := await get_user(session.id, user_id):
        # 当此平台已经绑定了该用户时查看是否与将要绑定的用户相同
        if bind_user.id == old_user.id:
            await matcher.finish(f"您已经绑定了该用户咯")
        else:
            state["bind_user"] = bind_user
            state["old_user"] = old_user
            await matcher.send(
                f"您已经绑定了用户[{old_user.id}]\n是否需要解除绑定更换成[{bind_user.id}]呢? (是/否)"
            )
    else:
        await add_user_bind(session.id, user_id, bind_user)
        await matcher.finish(f"已将您绑定到用户[{bind_user.id}]")


@bind_token_cmd.got("is_ok")
async def _(
    state: T_State,
    matcher: Matcher,
    session: SessionPlatform,
    user_id: UserId,
    is_ok: str = ArgPlainText(),
):
    if is_ok == "是":
        bind_user: User = state["bind_user"]
        old_user: User = state["old_user"]
        await rebind_user(session.id, user_id, old_user, bind_user)
        await matcher.finish(f"已将您绑定到用户[{bind_user.id}]")
    await matcher.finish(f"已取消绑定")
