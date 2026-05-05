from uuid import uuid4
from datetime import datetime

from utils import Emoji
from nonebot.adapters import Event
from utils.config import global_config
from utils.session import EventSession
from nonebot.params import ArgPlainText
from nonebot_plugin_waiter import waiter
from nonebot_plugin_alconna import AlconnaMatcher
from utils.roles import JoinMethod, TeacherClassesRole
from utils.models import (
    Group,
    User,
    School,
    Student,
    Classes,
    College,
    Major,
    Teacher,
    GroupBind,
    StudentExtra,
    ClassesJoinRequest,
)
from utils.models.depends import StudentDepends, TeacherDepends, UserOrCreatedDepends

from .depends import ImportDataFrame
from .util import student_column_renames, student_column_required
from .constants import JOIN_METHOD_MAPPING, JOIN_REQUEST_ACTION_MAPPING
from .importing import normalize_cell, normalize_datetime, get_student_by_student_code, build_user_update_payload
from .presenters import get_join_method_label, render_classes_card, render_join_request_card
from .services import ensure_teacher_scope, resolve_class_scope, resolve_teacher_request_scope
from .commands import (
    exit_classes_cmd,
    join_classes_cmd,
    query_classes_cmd,
    create_classes_cmd,
    delete_classes_cmd,
    import_classes_cmd,
    set_join_classes_cmd,
    query_join_request_cmd,
    review_join_request_cmd,
)


@import_classes_cmd.handle()
async def _(matcher: AlconnaMatcher, df: ImportDataFrame, user: UserOrCreatedDepends):
    """批量导入班级与学生信息。"""
    if df is None:
        await matcher.finish(Emoji.error + "未识别到有效的导入文件，请重新上传 Excel 文件。")
    if user.student is not None:
        await matcher.finish(Emoji.error + "您是学生，没有权限导入班级信息！！")
    if missing_columns := student_column_required - set(df.columns):
        await matcher.finish(
            Emoji.error + f"缺少列: {', '.join(student_column_renames[i][0] for i in missing_columns)}"
        )

    normalized_rows: list[dict[str, str | datetime | None]] = []
    invalid_rows: list[str] = []
    for index, row in df.iterrows():
        normalized_row = {
            "name": normalize_cell(row.get("name")),
            "student_code": normalize_cell(row.get("student_id")),
            "school": normalize_cell(row.get("school")),
            "college": normalize_cell(row.get("college")),
            "classes": normalize_cell(row.get("classes")),
            "major": normalize_cell(row.get("major")),
            "sex": normalize_cell(row.get("sex")),
            "nation": normalize_cell(row.get("nation")),
            "phone": normalize_cell(row.get("phone")),
            "email": normalize_cell(row.get("email")) if "email" in df.columns else None,
            "political_status": normalize_cell(row.get("political_status")),
            "family_address": normalize_cell(row.get("family_address")),
            "family_contact": normalize_cell(row.get("family_contact")),
            "dormitory": normalize_cell(row.get("dormitory")),
            "birthday": normalize_datetime(row.get("birthday")),
        }
        missing = [
            student_column_renames[column][0]
            for column in student_column_required
            if normalized_row["student_code" if column == "student_id" else column] is None
        ]
        if missing:
            invalid_rows.append(f"第{index + 2}行缺少字段: {', '.join(missing)}")
            continue
        normalized_rows.append(normalized_row)

    if invalid_rows:
        await matcher.finish(Emoji.error + "导入数据存在空值问题：\n" + "\n".join(invalid_rows[:10]))

    teacher = user.teacher
    summary = {
        "created_classes": 0,
        "updated_classes": 0,
        "bound_classes": 0,
        "created_students": 0,
        "updated_students": 0,
        "skipped_user_conflicts": 0,
    }

    grouped: dict[str, dict[str, dict[str, list[dict[str, str | datetime | None]]]]] = {}
    for row in normalized_rows:
        grouped.setdefault(row["school"], {}).setdefault(row["college"], {}).setdefault(row["classes"], []).append(row)

    for school_name, college_map in grouped.items():
        school = await School.filter(name=school_name).first()
        if school is None:
            await matcher.finish(Emoji.error + f"学校`{school_name}`不存在")

        if teacher is None:
            teacher = await Teacher.create_teacher(user.nickname, user, school_id=school.id)
        elif teacher.school_id is None:
            teacher = await teacher.update(school_id=school.id)
        elif teacher.school_id != school.id:
            await matcher.finish(Emoji.error + f"您的教师归属学校为`{teacher.school.name}`，不能导入其他学校的数据。")

        for college_name, classes_map in college_map.items():
            college = await College.filter(name=college_name, school_id=school.id).first()
            if college is None:
                college = await College(name=college_name, school_id=school.id).create()

            if teacher.college_id is not None and teacher.college_id != college.id:
                await matcher.finish(
                    Emoji.error + f"您的教师归属学院为`{teacher.college.name}`，不能导入其他学院的数据。"
                )

            for classes_name, rows in classes_map.items():
                major_values = sorted({row["major"] for row in rows if row["major"]})
                if len(major_values) > 1:
                    await matcher.finish(
                        Emoji.error + f"班级`{classes_name}`存在多个专业值：{'、'.join(major_values)}，请先整理导入表。"
                    )
                major_name = major_values[0] if major_values else None
                major = await Major.get_or_create_major(major_name, college) if major_name else None

                classes = await Classes.filter(name=classes_name, college_id=college.id).first()
                if classes is None:
                    group = await Group.create_group(str(classes_name), user)
                    classes = await Classes(
                        name=classes_name,
                        group=group,
                        school_id=school.id,
                        college_id=college.id,
                        major=major_name,
                        major_id=major.id if major else None,
                    ).create()
                    await classes.bind_teacher(teacher)
                    await classes.update_teacher_role(teacher, TeacherClassesRole.counselor)
                    summary["created_classes"] += 1
                    summary["bound_classes"] += 1
                else:
                    if classes.school_id is not None and classes.school_id != school.id:
                        await matcher.finish(
                            Emoji.error + f"班级`{classes_name}`已归属学校`{classes.school.name}`，与导入数据冲突。"
                        )
                    if classes.major_id is not None and major is not None and classes.major_id != major.id:
                        current_major = classes.major_ref.name if classes.major_ref else (classes.major or "未设置")
                        await matcher.finish(
                            Emoji.error + f"班级`{classes_name}`已绑定专业`{current_major}`，与导入数据冲突。"
                        )

                    payload = {}
                    if classes.school_id is None:
                        payload["school_id"] = school.id
                    if classes.college_id is None:
                        payload["college_id"] = college.id
                    if major_name and classes.major is None:
                        payload["major"] = major_name
                    if major and classes.major_id is None:
                        payload["major_id"] = major.id
                    if payload:
                        classes = await classes.update(**payload)
                        summary["updated_classes"] += 1

                    teacher_ids = [item.id for item in classes.teacher]
                    if teacher.id not in teacher_ids:
                        if teacher_ids:
                            await matcher.finish(
                                Emoji.error + f"班级`{classes_name}`已存在且不归您管理，无法导入该班级的学生数据。"
                            )
                        await classes.bind_teacher(teacher)
                        await classes.update_teacher_role(teacher, TeacherClassesRole.counselor)
                        summary["bound_classes"] += 1

                for row in rows:
                    student = await get_student_by_student_code(row["student_code"])
                    if student is None:
                        new_user = await User.create_user(nickname=row["name"], username=uuid4().hex[:16])
                        student = await Student.create_student(row["name"], classes, new_user, school_id=school.id)
                        summary["created_students"] += 1
                    else:
                        payload = {}
                        if row["name"] and row["name"] != student.name:
                            payload["name"] = row["name"]
                        if student.classes_id != classes.id:
                            payload["classes_id"] = classes.id
                        if student.school_id != school.id:
                            payload["school_id"] = school.id
                        if payload:
                            student = await student.update(**payload)
                        summary["updated_students"] += 1

                    extra = student.extra if student.extra else await StudentExtra(student=student).create()
                    extra_payload = {}
                    for field in (
                        "student_code",
                        "dormitory",
                        "political_status",
                        "family_contact",
                        "family_address",
                        "nation",
                    ):
                        value = row.get(field)
                        if value and value != getattr(extra, field):
                            extra_payload[field] = value
                    if extra_payload:
                        await extra.update(**extra_payload)

                    user_payload, skipped_conflicts = await build_user_update_payload(student.user, row)
                    summary["skipped_user_conflicts"] += skipped_conflicts
                    if user_payload:
                        await student.user.update(**user_payload)

    await matcher.finish(
        Emoji.success
        + "班级导入完成！\n"
        + f"{Emoji.info}创建班级: {summary['created_classes']}\n"
        + f"{Emoji.info}更新班级: {summary['updated_classes']}\n"
        + f"{Emoji.info}绑定班级: {summary['bound_classes']}\n"
        + f"{Emoji.info}创建学生: {summary['created_students']}\n"
        + f"{Emoji.info}更新学生: {summary['updated_students']}\n"
        + f"{Emoji.info}跳过重复手机号/邮箱: {summary['skipped_user_conflicts']}"
    )


@create_classes_cmd.handle()
async def _(
    class_name: str,
    school_name: str | None,
    college_name: str | None,
    major_name: str | None,
    platform: EventSession,
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
):
    """处理当前命令或事件逻辑。"""
    if user.student is not None:
        await matcher.finish(Emoji.error + "您是学生没有权限创建班级！！")
    elif not platform.is_group:
        await matcher.finish(Emoji.error + "请在群聊中使用该命令！！")
    elif classes := await Classes.get_classes(platform.platform, platform.channel_id, platform.guild_id):
        await matcher.finish(Emoji.error + f"这个群已经是班级群了！！\n> 班级ID: {classes.id}\n> 名称: {classes.name}")
    elif platform.channel_id is None:
        await matcher.finish(Emoji.error + "请在子频道中使用该命令！！")

    teacher = user.teacher
    school, college, major = await resolve_class_scope(matcher, teacher, school_name, college_name, major_name)
    if teacher is None:
        teacher = await Teacher.create_teacher(
            user.nickname,
            user,
            school_id=school.id if school else None,
            college_id=college.id if college else None,
        )
    else:
        teacher = await ensure_teacher_scope(teacher, school, college)
    if len(teacher.classes) >= global_config.teacher_max_classes:
        await matcher.finish(Emoji.error + "您所管理的班级数量已经超过上限！！")
    if classes := await teacher.get_classes(class_name):
        payload = {}
        if school:
            if classes.school_id and classes.school_id != school.id:
                await matcher.finish(
                    Emoji.error + f"班级`{class_name}`已归属于学校`{classes.school.name}`，不能重新绑定到其他学校。"
                )
            if classes.school_id is None:
                payload["school_id"] = school.id
        if college:
            if classes.college_id and classes.college_id != college.id:
                await matcher.finish(
                    Emoji.error + f"班级`{class_name}`已归属于学院`{classes.college.name}`，不能重新绑定到其他学院。"
                )
            if classes.college_id is None:
                payload["college_id"] = college.id
        if major:
            if classes.major_id and classes.major_id != major.id:
                current_major = classes.major_ref.name if classes.major_ref else (classes.major or "未设置")
                await matcher.finish(
                    Emoji.error + f"班级`{class_name}`已绑定专业`{current_major}`，不能重新绑定到其他专业。"
                )
            if classes.major_id is None:
                payload["major_id"] = major.id
                payload["major"] = major.name
        if payload:
            classes = await classes.update(**payload)
        # 如果教师班级已存在并且该群未绑定班级就按照名字绑定班级
        await GroupBind.bind_group(
            platform_name=platform.platform_name,
            platform_id=platform.platform,
            channel_id=platform.channel_id,
            guild_id=platform.guild_id,
            group=classes.group,
        )
        await matcher.finish(await render_classes_card("班级绑定成功", [classes]))
    else:
        classes = await Classes.create_classes(
            class_name,
            platform_name=platform.platform_name,
            platform_id=platform.platform,
            channel_id=platform.channel_id,
            guild_id=platform.guild_id,
            user=user,
            school_id=school.id if school else teacher.school_id,
            college_id=college.id if college else teacher.college_id,
            major=major.name if major else None,
            major_id=major.id if major else None,
        )
        await classes.bind_teacher(teacher)
        await classes.update_teacher_role(teacher, TeacherClassesRole.counselor)
        await matcher.finish(await render_classes_card("班级创建成功", [classes]))


@delete_classes_cmd.handle()
async def _(
    classes_id: int | None,
    platform: EventSession,
    matcher: AlconnaMatcher,
    teacher: TeacherDepends,
):
    """处理当前命令或事件逻辑。"""
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
            """检查yes。"""
            return event.get_message().extract_plain_text().lower() == "yes"

        if not await is_yes.wait(timeout=60):
            await matcher.finish("❌️已取消操作！！")

    # 先删除班级主体，再清理其挂载的群组与设置，
    # 避免直接删除 Group 时 SQLAlchemy 先把 classes.group_id 置空，
    # 从而触发 `bot_classes.group_id` 的非空约束错误。
    group = classes.group
    settings = group.settings
    await classes.filter(id=classes.id).delete()
    await group.filter(id=group.id).delete()
    if settings is not None:
        await settings.filter(id=settings.id).delete()
    await matcher.finish("✅️删除班级成功！！")


@query_classes_cmd.handle()
async def _(
    classes_id: int | None,
    teacher: TeacherDepends,
    matcher: AlconnaMatcher,
):
    """处理当前命令或事件逻辑。"""
    if teacher is None or not teacher.classes:
        await matcher.finish(Emoji.warning + "您还未创建班级！！")
    if classes_id is not None:
        classes = await teacher.get_classes(classes_id)
        if classes is None:
            await matcher.finish(Emoji.error + f"班级[{classes_id}]不存在，或不属于您管理。")
        await matcher.finish(await render_classes_card("班级详情", [classes]))
    await matcher.finish(await render_classes_card("您所管理的班级如下", list(teacher.classes)))


@query_join_request_cmd.handle()
async def _(
    classes_id: int | None,
    teacher: TeacherDepends,
    platform: EventSession,
    matcher: AlconnaMatcher,
):
    """查询入班申请。"""
    classes_list = await resolve_teacher_request_scope(matcher, teacher, platform, classes_id)
    requests: list[ClassesJoinRequest] = []
    for classes in classes_list:
        requests.extend(await classes.get_join_requests())

    if not requests:
        title = "当前班级暂无待处理入班申请" if len(classes_list) == 1 else "当前没有待处理入班申请"
        await matcher.finish(Emoji.success + title)

    requests.sort(key=lambda item: item.created_at)
    title = f"入班申请 | {classes_list[0].name}" if len(classes_list) == 1 else "入班申请列表"
    await matcher.finish(await render_join_request_card(title, requests))


@review_join_request_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    teacher: TeacherDepends,
    request_id: int,
    action: str,
):
    """处理入班申请。"""
    if teacher is None or not teacher.classes:
        await matcher.finish(Emoji.warning + "您还未创建班级！！")

    request = await ClassesJoinRequest.filter(id=request_id).first()
    if request is None:
        await matcher.finish(Emoji.error + f"入班申请[{request_id}]不存在。")

    if request.classes.id not in [classes.id for classes in teacher.classes]:
        await matcher.finish(Emoji.error + "该入班申请不属于您管理的班级。")

    normalized_action = JOIN_REQUEST_ACTION_MAPPING.get(action.strip().lower())
    if normalized_action is None:
        await matcher.finish(Emoji.error + "处理结果只支持：通过 或 拒绝。")

    if normalized_action == "approve":
        if request.user.student and request.user.student.classes_id == request.classes_id:
            await request.delete()
            await matcher.finish(Emoji.warning + "该用户已经在班级中，已自动清理重复申请。")
        await request.classes.user_join_classes(request.user)
        await request.delete()
        await matcher.finish(
            Emoji.success
            + f"已通过申请[{request.id}]，用户`{request.user.nickname}`已加入班级`{request.classes.name}`。"
        )

    await request.delete()
    await matcher.finish(Emoji.success + f"已拒绝申请[{request.id}]。")


# --------------------------------- 加入班级 ---------------------------------


@join_classes_cmd.handle()
async def _(
    describe: str | None,
    classes_id: int | None,
    event: Event,
    platform: EventSession,
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
):
    """处理当前命令或事件逻辑。"""
    matcher.state["describe"] = describe

    if user.teacher is not None:
        await matcher.finish(Emoji.error + "您是教师没有权限加入班级！！")
    elif classes_id:  # 如果有班级ID则查询班级信息
        if (classes := await Classes.get_classes(classes_id)) is None:
            await matcher.finish(f"❌️班级[{classes_id}]不存在！！")
    elif platform.is_group:  # 如果是群聊则查询群是否是班级群
        if (classes := await Classes.get_classes(platform.platform, platform.channel_id, platform.guild_id)) is None:
            await matcher.finish("❌️该群不是班级群！！")
    else:  # 如果不是群聊则提示需要班级ID
        await matcher.finish("❌️请在群聊中使用该命令或命令后面携带班级ID，例如:\n加入班级 1！！")

    matcher.state["classes"] = classes
    if user.student is not None:  # 已经是学生说明已经加入过班级
        if user.student.classes_id == classes.id:
            await matcher.finish("❌️您已经该班级中的一员！！")
        return

    # 未加入班级时无需额外确认，直接给 got 参数注入 yes，
    # 既保留统一的后续加入逻辑，也兼容 nonebug / 多适配器场景。
    matcher.set_arg("is_join", event.get_message().__class__("yes"))


@join_classes_cmd.got("is_join", prompt="您已经加入过其它班级，是否需要修改您的班级？(yes/no)")
async def _(
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
    is_join: str = ArgPlainText(),
):
    """处理当前命令或事件逻辑。"""
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
    """处理当前命令或事件逻辑。"""
    if student is None:
        await matcher.finish("❌️您还未加入班级！！")
    await matcher.send(
        f"您当前所在班级为**{student.classes.name}**，班级ID为**{student.classes.id}**，" "是否要退出该班级？(yes/no)"
    )


@exit_classes_cmd.got("is_exit")
async def _(matcher: AlconnaMatcher, student: StudentDepends, is_exit: str = ArgPlainText()):
    """处理当前命令或事件逻辑。"""
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
    """处理当前命令或事件逻辑。"""
    if teacher is None or not teacher.classes:
        await matcher.finish("❌️您还未创建班级！！")

    if classes_id and classes_id.strip() in JOIN_METHOD_MAPPING and join_method is None:
        join_method = classes_id
        classes_id = None

    if join_method is None:
        await matcher.finish("❌️请提供加入方式，例如：修改班级加入方式 1 申请加入")

    join_method_value = JOIN_METHOD_MAPPING.get(join_method.strip().lower())
    if join_method_value is None:
        await matcher.finish("❌️加入班级方式不存在！！\n只支持设置为：直接通过、申请加入、邀请加入")

    classes: Classes | None = None
    if classes_id is None:
        if platform.is_private:
            await matcher.finish("❌️私聊中请携带班级ID，例如：修改班级加入方式 1 申请加入")
        classes = await teacher.get_classes(platform.platform, platform.channel_id, platform.guild_id)
        if classes is None:
            await matcher.finish("❌️当前群不是您管理的班级群！！")
    else:
        if not classes_id.isdigit():
            await matcher.finish("❌️班级ID必须为数字！！")
        classes = await Classes.get_classes(int(classes_id))
        if classes is None:
            await matcher.finish(f"❌️班级[{classes_id}]不存在！！")
        if classes.id not in [cid.id for cid in teacher.classes]:
            await matcher.finish("❌️该班级不属于您！！")

    if classes.group.settings.join_method == join_method_value:
        await matcher.finish(f"❌️当前班级加入方式已经是：{get_join_method_label(join_method_value)}")

    await classes.group.settings.update(join_method=join_method_value)
    await matcher.finish(
        Emoji.success
        + f"已将班级[{classes.id}: {classes.name}]的加入方式修改为：{get_join_method_label(join_method_value)}"
    )
