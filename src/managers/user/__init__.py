from uuid import uuid4
from nonebot.matcher import Matcher
from nonebot.params import EventPlainText, ArgPlainText
from nonebot_plugin_alconna import AlconnaMatcher, UniMessage

from utils.cache import get_cache
from utils.models.annotated import UserOrCreatedDepends, UserDepends
from utils.models import User, Bind
from utils.session import EventSession

from .commands import self_info_cmd, bind_user_cmd, token_cmd


@self_info_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends):
    await matcher.finish(
        UniMessage.image(url=user.avatar)
        + UniMessage(
            f"用户信息：\n"
            f"ID：{user.id}\n"
            f"昵称：{user.nickname}\n"
            f"用户名：{user.username}\n"
            f"邮箱：{user.email}"
        )
    )


@bind_user_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends):
    # 生成随机token写入缓存作为key，user_id作为value，超时时间为5分钟
    cache = get_cache()
    token = str(uuid4())
    await cache.set(token, user.id, ex=300)
    await matcher.finish(
        UniMessage(
            (
                f"需要绑定平台请在5分钟内将以下token粘贴到指定平台发送:\n"
                f"token={token}"
            )
        )
    )


@token_cmd.handle()
async def _(
    matcher: Matcher,
    user: UserDepends,
    token: str = EventPlainText(),
):
    # 切割开头的token=，获取token
    token = token.strip()[6:]
    cache = get_cache()
    bind_user_id = await cache.get(token)

    # 检查token是否存在
    if bind_user_id is None:
        await matcher.finish("token不存在或者已过期，请重新获取")
    await cache.delete(token)

    matcher.state["bind_user_id"] = int(bind_user_id)

    if user is None:
        matcher.state["confirm"] = UniMessage("yes")
    else:
        await matcher.send(
            f'您已经在该平台绑定过id为"{user.id}"的账号，是否要重新绑定？(yes/no)'
        )


@token_cmd.got("confirm")
async def _(
    matcher: Matcher,
    platform: EventSession,
    confirm: str = ArgPlainText(),
):
    if confirm.lower() != "yes":
        await matcher.finish("已取消绑定")

    # 当前需要绑定的用户是否存在（一般都存在，除非某些不可抗力）
    bind_user: User | None = await User.get_user(matcher.state["bind_user_id"])
    if bind_user is None:
        await matcher.finish("绑定用户不存在,可能已经被删除！")

    # 获取旧的绑定信息并删除
    if bind := await Bind.get_bind(platform.platform, platform.user_id):
        await bind.delete()

    await Bind.bind_user(
        platform.platform,
        platform.user_id,
        bind_user,
    )
    await matcher.finish("绑定成功")
