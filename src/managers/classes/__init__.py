from nonebot.params import ArgPlainText
from nonebot_plugin_alconna import AlconnaMatcher, UniMessage

from utils.session import EventSession
from utils.models import Classes, GroupBind, Student
from utils.models.annotated import (
    TeacherDepends,
    UserOrCreatedDepends,
    TeacherOrCreatedDepends,
)
from .commands import add_classes_cmd, query_classes_cmd, join_classes_cmd


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
        await classes.bind_teacher(teacher)
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


@join_classes_cmd.handle()
async def _(
    platform: EventSession,
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
    classes_id: int | None,
):
    if classes_id:  # 如果有班级ID则查询班级信息
        if (classes := await Classes.get_classes(classes_id)) is None:
            await matcher.finish(f"❌️班级[{classes_id}]不存在！！")
    elif platform.is_group():  # 如果是群聊则查询群是否是班级群
        if (classes := await Classes.get_classes(**platform.group_params)) is None:
            await matcher.finish("❌️该群不是班级群！！")
    else:  # 如果不是群聊则提示需要班级ID
        await matcher.finish(
            "❌️请在群聊中使用该命令或命令后面携带班级ID，例如:\n添加班级 1！！"
        )

    if user.student is not None:  # 已经是学生说明已经加入过班级
        if user.student.classes_id == classes.id:
            await matcher.finish("❌️您已经该班级中的一员！！")
    else:  # 未加入班级则不询问是否需要修改班级
        matcher.state["is_join"] = UniMessage("yes")

    matcher.state["classes"] = classes


@join_classes_cmd.got(
    "is_join", prompt="您已经加入过其它班级，是否需要修改您的班级？(yes/no)"
)
async def _(
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
    is_join: str = ArgPlainText(),
):
    if is_join.strip() != "yes":
        await matcher.finish("❌️已取消操作！！")

    if (classes := matcher.state.get("classes")) is None:
        await matcher.finish("❌️[异常]未找到班级！！")

    if user.student is None:  # 创建学生
        await Student.create_student(user.nickname, classes, user)
    else:  # 如果已经是学生则更新班级
        await user.student.update_classes(classes)

    await matcher.finish(f"✅️成功加入班级[{classes.id}: {classes.name}]！！")
