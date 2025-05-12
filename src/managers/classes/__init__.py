from utils import Emoji
from nonebot.adapters import Event
from utils.tools import StringCard
from utils.config import global_config
from utils.session import EventSession
from nonebot.params import ArgPlainText
from utils.models.models import Student
from nonebot_plugin_waiter import waiter
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher
from utils.roles import UserRole, JoinMethod, TeacherClassesRole
from utils.models import Group, School, Classes, College, Teacher, GroupBind
from utils.models.depends import StudentDepends, TeacherDepends, UserOrCreatedDepends

from .depends import ImportDataFrame
from .util import student_column_renames, student_column_required
from .commands import (
    exit_classes_cmd,
    join_classes_cmd,
    query_classes_cmd,
    create_classes_cmd,
    delete_classes_cmd,
    import_classes_cmd,
    set_join_classes_cmd,
)


@import_classes_cmd.handle()
async def _(matcher: AlconnaMatcher, df: ImportDataFrame, user: UserOrCreatedDepends):
    # print(df.columns)
    # print(df.head())

    # 检索出不在student_column_renames中的列
    if missing_columns := student_column_required - set(df.columns):
        await matcher.finish(Emoji.error + f"缺少列: {', '.join(student_column_renames[i][0] for i in missing_columns)}")

    for school_name, school_df in df.groupby("school"):
        if not (school := await School.filter(name=school_name).first()):
            await matcher.finish(Emoji.error + f"学校`{school_name}`不存在")
        # 检查college是否存在于数据库
        for college_name, college_df in school_df.groupby("college"):
            if not (college := await College.filter(name=college_name, school=school).first()):
                college = await College(name=college_name, school=school).create()
            for classes_name, classes_df in college_df.groupby("classes"):
                # 检查班级是否存在于数据库，不存在则创建
                if not (classes := await Classes.filter(name=classes_name, college_id=college.id).first()):
                    # 获取班级中的专业
                    if "major" not in classes_df or classes_df.major.isnull().all():
                        major = None
                    else:
                        major = classes_df.major.unique()
                        major = major[0] if len(major) == 1 else None

                    group = await Group.create_group(str(classes_name), user)
                    classes = await Classes(name=classes_name, group=group, college_id=college.id, major=major).create()

                for index, value in classes_df.iterrows():
                    print(index, value)
                    student = await Student.filter(student_code=value["student_code"]).first()
                    # student = await Student.create_student(
                    #     name=value["name"],
                    #     classes=classes,

                    # )
                # print(classes, classes_df)


@create_classes_cmd.handle()
async def _(
    class_name: str,
    platform: EventSession,
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
):
    if user.role == UserRole.student:
        await matcher.finish(Emoji.error + "您是学生没有权限创建班级！！")
    elif not platform.is_group:
        await matcher.finish(Emoji.error + "请在群聊中使用该命令！！")
    elif classes := await Classes.get_classes(platform.platform, platform.channel_id, platform.guild_id):
        await matcher.finish(Emoji.error + f"这个群已经是班级群了！！\n> 班级ID: {classes.id}\n> 名称: {classes.name}")
    elif platform.channel_id is None:
        await matcher.finish(Emoji.error + "请在子频道中使用该命令！！")

    teacher = user.teacher if user.teacher else await Teacher.create_teacher(user.nickname, user)
    if len(teacher.classes) >= global_config.teacher_max_classes:
        await matcher.finish(Emoji.error + "您所管理的班级数量已经超过上限！！")
    if classes := await teacher.get_classes(class_name):
        # 如果教师班级已存在并且该群未绑定班级就按照名字绑定班级
        await GroupBind.bind_group(
            platform_name=platform.platform_name,
            platform_id=platform.platform,
            channel_id=platform.channel_id,
            guild_id=platform.guild_id,
            group=classes.group,
        )
        await matcher.finish(
            f"{Emoji.info}班级ID: {classes.id}\n{Emoji.info}名称:{class_name}\n{Emoji.success}与本群绑定成功!{Emoji.win}"
        )
    else:
        classes = await Classes.create_classes(
            class_name,
            platform_name=platform.platform_name,
            platform_id=platform.platform,
            channel_id=platform.channel_id,
            guild_id=platform.guild_id,
            user=user,
        )
        await classes.bind_teacher(teacher)
        await classes.update_teacher_role(teacher, TeacherClassesRole.counselor)
        await matcher.finish(
            f"{Emoji.info}班级ID: {classes.id}\n{Emoji.info}名称:{class_name}\n{Emoji.success}创建成功!{Emoji.win}"
        )


@delete_classes_cmd.handle()
async def _(
    classes_id: int | None,
    platform: EventSession,
    matcher: AlconnaMatcher,
    teacher: TeacherDepends,
):
    if teacher is None:
        await matcher.finish(Emoji.error + "您还不是教师，没有可删除班级！！")
    elif classes_id is None and platform.is_private:
        await matcher.finish("❌️请在群聊中使用该命令或命令后面携带班级ID，例如:\n删除班级 1！！")

    if classes_id is None:
        if (classes := await teacher.get_classes(platform.platform, platform.channel_id, platform.guild_id)) is None:
            await matcher.finish("❌️该群不是你的班级群！！")
    else:
        if (classes := await Classes.get_classes(classes_id)) is None:
            await matcher.finish(f"❌️班级**{classes_id}**不存在！！")
        elif classes.id not in [cid.id for cid in teacher.classes]:
            await matcher.finish("❌️该班级不属于您！！")

    if await classes.student_count() > 0:
        await matcher.send("该班级中还有学生，您确定要删除吗？(yes/no)")

        @waiter(waits=["message"], block=True)
        async def is_yes(event: Event):
            return event.get_message().extract_plain_text().lower() == "yes"

        if not await is_yes.wait(timeout=60):
            await matcher.finish("❌️已取消操作！！")

    await Classes.filter(id=classes.id).delete()
    await matcher.finish("✅️删除班级成功！！")


@query_classes_cmd.handle()
async def _(
    teacher: TeacherDepends,
    matcher: AlconnaMatcher,
):
    if teacher is None or not teacher.classes:
        await matcher.finish(Emoji.warning + "您还未创建班级！！")
    card = StringCard("您所创建班级如下")
    for classes in teacher.classes:
        (
            card.hr()
            .text(f"班级ID: {classes.id}")
            .text(f"班级名称: {classes.name}")
            .text(f"学生数量: {await classes.student_count()}")
        )
    await matcher.finish(card.render())


# --------------------------------- 加入班级 ---------------------------------


@join_classes_cmd.handle()
async def _(
    describe: str | None,
    classes_id: int | None,
    platform: EventSession,
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
):
    matcher.state["describe"] = describe

    if user.role == UserRole.student:
        await matcher.finish(Emoji.error + "您已经加入过别的班级了！")
    elif user.role == UserRole.teacher:
        await matcher.finish(Emoji.error + "您是教师没有权限加入班级！！")
    elif classes_id:  # 如果有班级ID则查询班级信息
        if (classes := await Classes.get_classes(classes_id)) is None:
            await matcher.finish(f"❌️班级[{classes_id}]不存在！！")
    elif platform.is_group:  # 如果是群聊则查询群是否是班级群
        if (classes := await Classes.get_classes(platform.platform, platform.channel_id, platform.guild_id)) is None:
            await matcher.finish("❌️该群不是班级群！！")
    else:  # 如果不是群聊则提示需要班级ID
        await matcher.finish("❌️请在群聊中使用该命令或命令后面携带班级ID，例如:\n添加班级 1！！")

    if user.student is not None:  # 已经是学生说明已经加入过班级
        if user.student.classes_id == classes.id:
            await matcher.finish("❌️您已经该班级中的一员！！")
    else:  # 未加入班级则不询问是否需要修改班级
        matcher.state["is_join"] = UniMessage("yes")

    matcher.state["classes"] = classes


@join_classes_cmd.got("is_join", prompt="您已经加入过其它班级，是否需要修改您的班级？(yes/no)")
async def _(
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
    is_join: str = ArgPlainText(),
):
    classes: Classes | None
    if is_join.strip() != "yes":
        await matcher.finish("❌️已取消操作！！")

    if (classes := matcher.state.get("classes")) is None:
        await matcher.finish("❌️[异常]未找到班级！！")
    elif user.teacher is not None and user.teacher.id in [tid.id for tid in classes.teacher]:
        await matcher.finish("❌️您是班级的教师，无法加入该班级！！")

    match classes.group.settings.join_method:
        case JoinMethod.direct:
            await classes.user_join_classes(user)
            await matcher.finish(f"✅️成功加入班级[{classes.id}: {classes.name}]！！")
        case JoinMethod.apply:
            await classes.apply_join_classes(user, matcher.state.get("describe"))
            await matcher.finish("✅️申请成功，请等待班主任审核！！")
        case JoinMethod.invite:
            await matcher.finish("❌️该班级只能通过邀请加入！！")
    await matcher.finish("❌️[异常]加入班级失败！！")


# --------------------------------- 退出班级 ---------------------------------


@exit_classes_cmd.handle()
async def _(matcher: AlconnaMatcher, student: StudentDepends):
    if student is None:
        await matcher.finish("❌️您还未加入班级！！")


@exit_classes_cmd.got("is_exit", prompt="您确定要退出班级吗？(yes/no)")
async def _(matcher: AlconnaMatcher, student: StudentDepends, is_exit: str = ArgPlainText()):
    if is_exit.strip() != "yes":
        await matcher.finish("❌️已取消操作！！")

    if student:
        await student.filter(id=student.id).delete()
        await matcher.finish("✅️成功退出班级！！")
    await matcher.finish("❌️退出班级失败，您的身份似乎并不是学生！！")


# --------------------------------- 修改加入班级方式 ---------------------------------


@set_join_classes_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    teacher: TeacherDepends,
    classes_id: str | None,
    join_method: str | None,
    platform: EventSession,
):
    # 纠正classes_id和join_method
    if join_method is not None and join_method.isdigit():
        ...
    # if classes_id is not None and join_method is not None:
    #     if classes_id.isdigit():    # 当classes_id为数字时
    #         if join_method.isdigit():   # 当join_method也为数字时
    #             await matcher.finish("❌️加入班级方式不能为数字！！")
    #         elif join_method_dict.get(join_method) is None:
    #             await matcher.finish("❌️加入班级方式不存在！！\n只支持设置为：" + "、".join(join_method_dict.keys()))

    # if teacher is None or not teacher.classes:
    #     await matcher.finish("❌️您还未创建班级！！")
    # elif (
    #     classes_id is None and platform.is_private
    # ):  # 如果未携带班级ID且是私聊则提示需要班级ID
    #     await matcher.finish(
    #         "❌️请在群聊中使用该命令或命令后面携带班级ID与加入方式，例如:\n修改班级加入方式 1 申请加入！！"
    #     )
    # elif (
    #     platform.is_group
    #     and classes_id is None
    #     and (classes := await teacher.get_classes(**platform.group_params)) is None
    # ):  # 如果是群聊则查询群是否是班级群
    #     await matcher.finish("❌️该群不是您管辖的班级群！！")

    # if classes_id is not None and not classes_id.isdigit():
    #     await matcher.finish("❌️班级ID必须为数字！！")
