from typing import Annotated

from nonebot.params import Depends
from nonebot.typing import T_State
from utils.session import EventSession, GroupEventSession
from nonebot_plugin_userinfo import UserInfo, EventUserInfo
from utils.models.models import Bind, User, Classes, Student, Teacher

default_nickname = "user"


async def get_user_depends(
    platform: EventSession,
    state: T_State,
) -> User | None:
    """通过平台与用户信息获取用户"""
    if user := state.get("user_model"):
        return user
    elif user := await Bind.get_user(platform.platform, platform.user_id):
        state["user_model"] = user
        return user


UserDepends = Annotated[User | None, Depends(get_user_depends)]


async def get_user_or_create_depends(
    user: UserDepends,
    platform: EventSession,
    user_info: UserInfo | None = EventUserInfo(),
) -> User:
    """通过平台与用户信息获取用户，若不存在则创建"""
    if user is None:
        if user_info:
            avatar = user_info.user_avatar
            user = await User.create_user(
                nickname=user_info.user_name.strip() or default_nickname,
                username=user_info.user_id,
                avatar=avatar.get_url() if avatar else None,
            )
        else:
            user = await User.create_user(
                nickname=default_nickname,
                username=platform.user_id,
            )
        await Bind.bind_user(platform.platform, platform.user_id, user)
    return user


UserOrCreatedDepends = Annotated[User, Depends(get_user_or_create_depends)]


async def teacher_depends(user: UserOrCreatedDepends) -> Teacher | None:
    return await Teacher.get_teacher(user)


TeacherDepends = Annotated[Teacher | None, Depends(teacher_depends)]


async def get_or_create_teacher_depends(user: UserOrCreatedDepends) -> Teacher:
    return await Teacher.get_or_create_teacher(user.nickname, user)


TeacherOrCreatedDepends = Annotated[Teacher, Depends(get_or_create_teacher_depends)]


async def get_classes(
    platform: GroupEventSession,
) -> Classes | None:
    """通过平台与群来查看是否是班级群"""
    return await Classes.get_classes(
        platform.platform, platform.channel_id, platform.guild_id
    )


ClassesDepends = Annotated[Classes | None, Depends(get_classes)]


async def teacher_classes(
    teacher: TeacherDepends,
    platform: EventSession,
) -> Classes | None:
    """查看当前群是否是教师的班级"""
    if teacher:
        return await teacher.get_classes(
            platform.platform, platform.channel_id, platform.guild_id
        )
    return None


TeacherClassesDepends = Annotated[Classes | None, Depends(teacher_classes)]


async def student_depends(
    user: UserOrCreatedDepends,
) -> Student | None:
    """查看是否是班级学生"""
    if user.student:
        return user.student
    return None


StudentDepends = Annotated[Student | None, Depends(student_depends)]
