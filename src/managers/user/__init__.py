from utils.models import User
from nonebot import on_command
from utils.params import UserId
from nonebot.typing import T_State
from nonebot.adapters import Message
from utils.session import SessionPlatform
from nonebot.internal.matcher import Matcher
from nonebot_plugin_alconna import on_alconna
from utils.auth.extension import UserExtension
from nonebot.params import CommandArg, ArgPlainText
from utils.typings import UserType, UserTypeChinese
from utils.models.depends import get_user, create_user, add_user_bind, remove_user_bind

from .bind_token import get_bind_data, get_bind_token

rules = {
    UserTypeChinese[rule]: rule
    for rule in [UserType.USER, UserType.STUDENT, UserType.TEACHER]
}


create_user_cmd = on_command("创建用户", aliases={"成为用户"}, block=True)
show_user_cmd = on_command("用户信息", aliases={"我的信息"}, block=True)
bind_user_cmd = on_alconna(
    "绑定用户",
    aliases={"绑定我的信息", "绑定信息", "绑定平台"},
    block=True,
    extensions=[UserExtension(True)],
)
bind_token_cmd = on_command("bind_token=", block=True)


# --------------------------------- 创建用户 ---------------------------------
@create_user_cmd.handle()
async def _(
    matcher: Matcher,
    session: SessionPlatform,
    user_id: str = UserId,
):
    if await get_user(session.id, user_id):
        await matcher.finish(f"您已经是用户了, 不要重复创建哦")
    elif user := await create_user(session.id, user_id, UserType.USER):
        await matcher.finish(f"已将您设置为用户, 您的用户id为[{user.id}]")


# --------------------------------- 用户信息 ---------------------------------
@show_user_cmd.handle()
async def _(
    matcher: Matcher,
    session: SessionPlatform,
    user_id: str = UserId,
):
    if user := await get_user(session.id, user_id):
        await matcher.finish(
            f"用户ID: {user.id}" f"\n用户类型: {UserTypeChinese[user.user_type]}"
        )
    else:
        await matcher.finish(f"您还不是用户哦, 请先发送[成为用户]命令")


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
    session: SessionPlatform,
    token: Message = CommandArg(),
    user_id: str = UserId,
):
    # 查看token是否正确
    bind_user_id = get_bind_data(token.extract_plain_text().strip())
    if bind_user_id is None:
        await matcher.finish()
    # 查看绑定用户是否存在
    bind_user = await get_user(bind_user_id)
    if bind_user is None:
        await matcher.finish("该用户已不存在!")
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
    session: SessionPlatform,
    user_id: str = UserId,
    is_ok: str = ArgPlainText(),
):
    if is_ok == "是":
        bind_user: User = state["bind_user"]
        old_user: User = state["old_user"]
        await remove_user_bind(session.id, user_id, old_user)  # 删除掉之前绑定的平台账号id
        await add_user_bind(session.id, user_id, bind_user)  # 绑定到该用户上
        await bind_token_cmd.finish(f"已将您绑定到用户[{bind_user.id}]")
