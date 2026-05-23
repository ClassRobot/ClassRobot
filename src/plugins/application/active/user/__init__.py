from uuid import uuid4

from src.shared import Emoji
from src.core.cache import get_cache
from nonebot.matcher import Matcher
from src.platform.session import EventSession
from src.models import User, UserBind
from src.core.auth import UserRole, UserRoleLang
from nonebot.params import ArgPlainText, EventPlainText
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher
from src.platform.session.depends import UserDepends, UserOrCreatedDepends

from .commands import token_cmd, logout_cmd, bind_user_cmd, self_info_cmd
from .presenters import render_user_card
# 导入统一命令 service，确保插件加载时完成 command_executor 注册。
from . import services as _


@self_info_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends):
    """处理当前命令或事件逻辑。"""
    card = await render_user_card(user)
    if user.avatar:
        await matcher.finish(UniMessage.image(url=user.avatar) + card)
    await matcher.finish(card)


@bind_user_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends):
    # 生成随机token写入缓存作为key，user_id作为value，超时时间为5分钟
    """处理当前命令或事件逻辑。"""
    cache = get_cache()
    token = str(uuid4())
    await cache.set(token, user.id, ex=300)
    await matcher.finish(UniMessage(f"需要绑定平台请在5分钟内将下方内容粘贴到指定平台发送:\ntoken={token}"))


@token_cmd.handle()
async def _(
    matcher: Matcher,
    user: UserDepends,
    token: str = EventPlainText(),
):
    # 切割开头的token=，获取token
    """处理当前命令或事件逻辑。"""
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
        await matcher.send(f"您已经在该平台绑定过[{user.id}:{user.username}]的账号，是否要重新绑定？(yes/no)")


@token_cmd.got("confirm")
async def _(
    matcher: Matcher,
    platform: EventSession,
    confirm: str = ArgPlainText(),
):
    """处理当前命令或事件逻辑。"""
    if confirm.strip().lower() != "yes":
        await matcher.finish("已取消绑定")

    # 当前需要绑定的用户是否存在（一般都存在，除非某些不可抗力）
    bind_user: User | None = await User.get_user(matcher.state["bind_user_id"])
    if bind_user is None:
        await matcher.finish("绑定用户不存在,可能已经被删除！")

    # 获取旧的绑定信息并删除
    if bind := await UserBind.get_bind(platform.platform, platform.user_id):
        await bind.delete()

    await UserBind.bind_user(
        platform.platform,
        platform.user_id,
        bind_user,
    )
    await matcher.finish("绑定成功")


@logout_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserDepends, role: str):
    """处理当前命令或事件逻辑。"""
    role = role.strip()
    if role not in [UserRoleLang.student, UserRoleLang.teacher, UserRoleLang.user]:
        await matcher.finish(Emoji.error + "角色不存在！")

    if user is None:
        await matcher.finish(Emoji.error + "您没有绑定任何账号！")
    elif role == UserRoleLang.teacher:
        if user.teacher is None:
            await matcher.finish(Emoji.error + "您没有绑定任何教师账号！")
        elif user.teacher.classes:
            await matcher.finish(Emoji.error + "请先退出班级或转让班级后再注销！")
    elif role == UserRoleLang.student:
        if user.student is None:
            await matcher.finish(Emoji.error + "您没有绑定任何学生账号！")
    elif role == UserRoleLang.user:
        if user.teacher is not None:
            await matcher.finish(Emoji.error + "请先注销教师账号后再注销！")
        elif user.student is not None:
            await matcher.finish(Emoji.error + "请先注销学生账号后再注销！")

    # 把待注销的目标角色写入 matcher state，
    # 由下一轮确认消息统一执行删除，避免把副作用耦合在 waiter 回调里。
    matcher.state["logout_role"] = role
    await matcher.send(Emoji.warning + f"您确定要注销**{role}**账号吗？\n" f"注销后将无法恢复，是否继续？(yes/no)")


@logout_cmd.got("confirm")
async def _(matcher: AlconnaMatcher, user: UserDepends, confirm: str = ArgPlainText()):
    """确认并执行注销逻辑。"""
    if confirm.strip().lower() != "yes":
        await matcher.finish(Emoji.warning + "注销已取消！")

    role = matcher.state.get("logout_role")
    if role is None:
        await matcher.finish(Emoji.error + "未找到待注销的角色信息，请重新发起注销命令。")
    if user is None:
        await matcher.finish(Emoji.error + "您没有绑定任何账号！")

    if role == UserRoleLang.teacher and user.teacher:
        next_role = UserRole.student if user.student is not None else UserRole.user
        await user.teacher.filter(id=user.teacher.id).delete()
        await user.update(role=next_role)
    elif role == UserRoleLang.student and user.student:
        next_role = UserRole.teacher if user.teacher is not None else UserRole.user
        await user.student.filter(id=user.student.id).delete()
        await user.update(role=next_role)
    elif role == UserRoleLang.user:
        await user.delete_account()
    else:
        await matcher.finish(Emoji.error + "目标账号不存在或已被注销，请刷新后重试。")

    await matcher.finish(Emoji.success + "注销成功！")
