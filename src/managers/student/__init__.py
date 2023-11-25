from utils.typings import UserType
from nonebot.matcher import Matcher
from utils.models.models import Teacher
from utils.models.depends import (
    get_user,
    get_student,
    create_student,
    delete_student,
    get_class_table,
)

from .params import ClassTableDepends
from .commands import add_student_cmd, del_student_cmd


@add_student_cmd.handle()
async def _(
    name: str,
    user_id: int,
    matcher: Matcher,
    teacher: Teacher,
    class_table: ClassTableDepends,
):
    if name.isdigit():  # 名称不能是数字
        await matcher.finish("姓名不能为纯数字！")
    elif (user := await get_user(user_id)) is None:  # 用户是否存在
        await matcher.finish(f"[{user_id}]用户不存在！")
    elif user.user_type == UserType.STUDENT or await get_student(user):  # 用户是否已经是学生
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
