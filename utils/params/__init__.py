from typing import Annotated

from nonebot.params import Depends
from nonebot.matcher import Matcher
from nonebot_plugin_alconna import At, Target
from nonebot.adapters import Event as BaseEvent
from utils.session.platform import SessionPlatform
from nonebot_plugin_alconna.uniseg import MsgTarget
from utils.models.models import User, Teacher, ClassTable
from utils.models.depends import get_user, create_user, get_class_table


def get_user_id(event: BaseEvent) -> str:
    return event.get_user_id()


def get_group_id(target: Target) -> str | None:
    if not target.private:
        return str(target.id) + (f"&{target.parent_id}" if target.parent_id else "")


async def _get_group_id(matcher: Matcher, target: MsgTarget) -> str:
    if group_id := get_group_id(target):
        return group_id
    await matcher.finish()


async def _teacher_class_table(
    matcher: Matcher, class_name_or_id: int | str, teacher: Teacher
) -> ClassTable:
    if class_table := await get_class_table(
        class_name_or_id, teacher=teacher
    ):  # 输入的班级是否存在
        print(class_table)
        return class_table
    await matcher.finish(f"[{class_name_or_id}]班级不存在！")


def _get_at_or_id_user(at_auto_create_user: bool = False):
    """当at的用户不存在时，是否自动创建用户"""

    async def _(
        matcher: Matcher, user_id_or_at: int | At, platform: SessionPlatform
    ) -> User:
        user: User | None = None
        if isinstance(user_id_or_at, At):  # 如果是at添加教师，先查看用户是否存在，如果不存在则创建用户后添加为教师
            if (
                user := await get_user(platform.id, user_id_or_at.target)
            ) is None and at_auto_create_user:
                user = await create_user(platform.id, user_id_or_at.target)
        else:
            user = await get_user(user_id_or_at)
        if user is None:
            await matcher.finish("该用户不存在哦！")
        return user

    return Depends(_)


UserId: str = Depends(get_user_id)
GroupId: str = Depends(_get_group_id)
TeacherClassTableDepends = Annotated[ClassTable, Depends(_teacher_class_table)]
UserIdOrAtParams = _get_at_or_id_user
