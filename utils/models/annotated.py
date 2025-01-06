from typing import Annotated, Optional

from nonebot.params import Depends
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_session import EventSession
from nonebot_plugin_userinfo import UserInfo, EventUserInfo

from utils.models.models import Classes, Teacher, User, Bind
default_nickname = "user"


async def get_user_depends(
    platform: EventSession,
    user_info: UserInfo = EventUserInfo(),
) -> User | None:
    """通过平台与用户信息获取用户"""
    return await Bind.get_user(platform.platform, user_info.user_id)


UserDepends = Annotated[User | None, Depends(get_user_depends)]


async def get_user_or_create_depends(
    platform: EventSession,
    user_info: UserInfo = EventUserInfo(),
) -> User:
    """通过平台与用户信息获取用户，若不存在则创建"""
    if user := await Bind.get_user(platform.platform, user_info.user_id):
        return user
    else:
        avatar = user_info.user_avatar
        user = await User.create_user(
            nickname=user_info.user_name.strip() or default_nickname,
            username=user_info.user_id,
            avatar=avatar.get_url() if avatar else None,
        )
        await Bind.bind_user(platform.platform, user_info.user_id, user)
        return user


UserOrCreatedDepends = Annotated[User, Depends(get_user_or_create_depends)]


# async def teacher_depends(
#     session: async_scoped_session,
#     user: UserOrCreatedDepends,
# ) -> Teacher | None:
#     return await Teacher.get_teacher(session, user)


# TeacherDepends = Annotated[Teacher | None, Depends(teacher_depends)]


# async def get_or_create_teacher_depends(
#     session: async_scoped_session,
#     user: UserOrCreatedDepends,
# ) -> Teacher:
#     return await Teacher.get_or_create_teacher(session, user, user.nickname)


# TeacherOrCreatedDepends = Annotated[Teacher, Depends(get_or_create_teacher_depends)]


# async def get_classes(
#     session: async_scoped_session,
#     platform: EventSession,
# ) -> Optional[Classes]:
#     """通过平台与群来查看是否是班级群"""
#     if not platform.id2:  # 是否为群聊
#         return
#     elif classes := await Classes.get_classes(session, platform.platform, platform.id2):
#         return classes


# ClassesDepends = Annotated[Classes | None, Depends(get_classes)]


# # async def get_teacher_classes(
# #     session: async_scoped_session,
# #     teacher: TeacherOrCreatedDepends,
# # ) -> list[Classes]:
# #     ...
