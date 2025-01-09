from nonebot_plugin_alconna import AlconnaMatcher
from nonebot_plugin_orm import async_scoped_session
from utils.session import EventSession

from utils.models import Classes, TeacherClasses, GroupBind
from utils.models.annotated import (
    UserOrCreatedDepends,
    TeacherOrCreatedDepends,
    ClassesDepends,
    TeacherDepends,
)
from .commands import add_classes_cmd, query_classes_cmd


@add_classes_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    teacher: TeacherOrCreatedDepends,
    class_name: str,
    platform: EventSession,
):
    if not platform.is_group():
        await matcher.finish("❌️请在群聊中使用该命令！！")
    elif classes := await Classes.get_classes(**platform.group_params):
        await matcher.finish(
            f"❌️这个群已经是班级群了！！\n> 班级ID: {classes.id}\n> 名称: {classes.name}"
        )
    if classes := await teacher.get_classes(class_name):
        # 如果教师班级已存在并且该群未绑定班级就按照名字绑定班级
        await GroupBind.bind_group(**platform.group_params, group=classes.group)
        await matcher.finish(
            f"✅️班级ID: {classes.id}\n✅️名称:{class_name}\n🥳与本群绑定成功!🎉"
        )
    else:
        classes = await Classes.create_classes(
            class_name,
            **platform.group_params,
            user=teacher.user,
        )
        await TeacherClasses.association(teacher, classes)
        await matcher.finish(
            f"✅️班级ID: {classes.id}\n✅️名称:{class_name}\n🥳创建成功!🎉"
        )


@query_classes_cmd.handle()
async def _(
    teacher: TeacherDepends,
    matcher: AlconnaMatcher,
):
    if teacher is None or not teacher.classes:
        await matcher.finish("❌️您还未创建班级！！")
    await matcher.finish(
        "您所创建班级如下:\n"
        + "\n-----".join(
            f"| 班级ID: {classes.id}\n| 班级名称: {classes.name}"
            for classes in teacher.classes
        )
    )
