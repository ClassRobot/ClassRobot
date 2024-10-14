from nonebot.matcher import Matcher
from utils.models.models import User, Teacher
from utils.typings import UserType, class_cadres
from utils.params.notes import ValidateNameNotNumeric
from utils.params import UserIdOrAtParams, TeacherClassTableDepends
from utils.models.depends import get_user, get_student, create_student, delete_student

from .commands import add_student_cmd, del_student_cmd, set_class_cadre_cmd


@add_student_cmd.handle()
async def _(
    user_id: int,
    matcher: Matcher,
    teacher: Teacher,
    name: ValidateNameNotNumeric,
    class_table: TeacherClassTableDepends,
):
    if (user := await get_user(user_id)) is None:  # 用户是否存在
        await matcher.finish(f"[{user_id}]用户不存在！")
    elif user.user_type == UserType.TEACHER:
        await matcher.finish(f"[{user_id}]用户是教师，不能设置为学生！")
    elif user.user_type == UserType.STUDENT or await get_student(
        user
    ):  # 用户是否已经是学生
        await matcher.finish(f"[{user_id}]用户已经是学生了！")

    student = await create_student(name, class_table, teacher, user)
    await matcher.finish(
        f"成功将[{student.name}]学生添加到[{class_table.name}]！这位学生的学生id为[{student.id}]"
    )


@del_student_cmd.handle()
async def _(matcher: Matcher, user_ids: set[str], teacher: Teacher):
    delete_list = []
    for uid in (int(i) for i in user_ids if i.isdigit()):
        if await delete_student(uid, teacher):
            delete_list.append(uid)
    if delete_list:
        await matcher.finish(f"成功将id为{delete_list}的学生移除！")
    await matcher.finish("您似乎没有这些学生哦！")


@set_class_cadre_cmd.handle()
async def _(
    matcher: Matcher,
    class_cadre: str,
    teacher: Teacher,
    student_user: User = UserIdOrAtParams(),
):
    if class_cadre not in class_cadres:
        await matcher.finish(f"没有[{class_cadre}]这个班干部哦！")
    elif (
        student := await get_student(student_user)
    ) is None or student.teacher_id == teacher.id:
        await matcher.finish("您似乎没有这位学生哦！")
