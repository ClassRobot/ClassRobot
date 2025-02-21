from uuid import uuid4

from utils.cache import get_cache
from utils.tools import StringCard
from nonebot.matcher import Matcher
from utils.models import Bind, User
from utils.session import EventSession
from utils.roles import StudentRoleLang
from nonebot.params import ArgPlainText, EventPlainText
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher
from utils.models.depends import UserDepends, UserOrCreatedDepends

from .commands import (
    token_cmd,
    bind_user_cmd,
    self_info_cmd,
    # __helpers__ as __helpers__,
)


@self_info_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends):
    card = (
        StringCard()
        .hr("用户信息")
        .text(f"UID: {user.id}")
        .text(f"昵称: {user.nickname}")
        .text(f"账号: {user.username}")
    )
    if user.email:
        card.text(f"邮箱: {user.email}")
    if user.phone:
        card.text(f"电话: {user.phone}")
    card.text(f"创建日期: {user.created_at.strftime('%Y-%m-%d')}")
    if user.teacher is not None:
        (
            card.hr("教师信息")
            .text(f"教师ID: {user.teacher.id}")
            .text(f"教师昵称: {user.teacher.name}")
            .text(f"班级数量: {len(user.teacher.classes)}")
            .text(f"创建日期: {user.teacher.created_at.strftime('%Y-%m-%d')}")
        )
    if user.student is not None:
        (
            card.hr("学生信息")
            .text(f"学生ID: {user.student.id}")
            .text(f"学生昵称: {user.student.name}")
        )

        if user.student.role in StudentRoleLang._member_names_:
            card.text(f"学生职位: {StudentRoleLang[user.student.role]}")
        else:
            card.text(f"学生职位: {user.student.role}(无效)")

        (
            card.text(f"所在班级: {user.student.classes.name}").text(
                f"创建日期: {user.student.created_at.strftime('%Y-%m-%d')}"
            )
        )

    if user.avatar:
        await matcher.finish(UniMessage.image(url=user.avatar) + card.render())
    await matcher.finish(card.render())


@bind_user_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends):
    # 生成随机token写入缓存作为key，user_id作为value，超时时间为5分钟
    cache = get_cache()
    token = str(uuid4())
    await cache.set(token, user.id, ex=300)
    await matcher.finish(
        UniMessage(
            (f"需要绑定平台请在5分钟内将下方内容粘贴到指定平台发送:\n" f"token={token}")
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
            f"您已经在该平台绑定过[{user.id}:{user.username}]的账号，是否要重新绑定？(yes/no)"
        )


@token_cmd.got("confirm")
async def _(
    matcher: Matcher,
    platform: EventSession,
    confirm: str = ArgPlainText(),
):
    if confirm.strip().lower() != "yes":
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
