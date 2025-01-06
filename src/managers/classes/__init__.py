from nonebot_plugin_alconna import AlconnaMatcher
from nonebot_plugin_orm import async_scoped_session
from nonebot_plugin_session import EventSession

from utils.models.annotated import UserOrCreatedDepends
from .commands import add_classes_cmd, query_classes_cmd, query_current_classes_cmd


# @add_classes_cmd.handle()
# async def _(
#     matcher: AlconnaMatcher,
#     teacher: TeacherOrCreatedDepends,
#     class_name: str,
#     platform: EventSession,
#     classes: ClassesDepends,
#     session: async_scoped_session,
# ):
#     print(class_name)
#     group_id = platform.id2
#     if not group_id:
#         await matcher.finish("❌️请在群聊中使用该命令！！")
#     elif classes is not None:
#         await matcher.finish("❌️这个群已经是班级群了！！")
#     elif class_name.isdigit():
#         await matcher.finish("❌️班级名称不能全是数字！！")

#     classes = await Classes.create_classes(session, class_name, teacher.user)
#     await ClassesBind.bind_classes(session, classes, platform.platform, group_id)
#     # 将班级与群关联
#     await TeacherClasses.association(session, teacher, classes)
#     # 将教师与班级关联
#     await matcher.finish(f"✅️班级ID: {classes.id}\n✅️名称:{class_name}\n🥳创建成功!🎉")


@query_classes_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
):
    print(user)


# @query_current_classes_cmd.handle()
# async def _(
#     matcher: AlconnaMatcher,
#     classes: ClassesDepends,
#     platform: EventSession,
# ):
#     group_id = platform.id2
#     if not group_id:
#         await matcher.finish("❌️请在群聊中使用该命令！！")
#     elif classes is None:
#         await matcher.finish("❌️这个群不是班级群！！")
#     await matcher.finish(
#         f"> 班级ID: {classes.id}\n> 名称:{classes.name}"
#     )
