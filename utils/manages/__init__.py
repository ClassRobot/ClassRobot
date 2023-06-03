from nonebot.params import Depends
from nonebot.matcher import Matcher
from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent
from nonebot.typing import T_State

from typing import List, Optional, Union

from utils.orm import (
    Teacher,
    Student,
    ClassTable,
)

from .config import ClassCadre

User = Union[Teacher, Student]


# 学生身份
async def student_depends(state: T_State, matcher: Matcher, event: Event):
    if student := await Student.objects.filter(qq=event.get_user_id()).afirst():
        state["student"] = student
        return student
    else:
        await matcher.finish()


# 班干部身份
def CLASS_CADRE(cadres: Optional[List[str]] = None):    # type: ignore
    """是否为班干部

    Args:
        cadres (Optional[List[str]], optional): 选择哪些班干部. Defaults to None.
            如果为None表示全部
            如果为str表示单个
            如果为list表示几位
    """
    if cadres is None:
        cadres = ClassCadre.to_list()
    elif isinstance(cadres, str):
        cadres = [cadres]
    async def _(state: T_State, matcher: Matcher, event: Event):
        if student := await Student.objects.filter(qq=event.get_user_id()).afirst():
            if student.position in cadres:
                state["student"] = student
                return student
        await matcher.finish()
    return Depends(_)


# 教师身份
async def teacher_depends(state: T_State, matcher: Matcher, event: Event):
    if teacher := await Teacher.objects.filter(qq=event.get_user_id()).afirst():
        state["teacher"] = teacher
        return teacher
    else:
        await matcher.finish()


# 是否为系统中的任何类型的用户
async def user_depends(state: T_State, matcher: Matcher, event: Event):
    user_id = event.get_user_id()
    for model in list((Student, Teacher)):
        if user := await model.objects.filter(qq=user_id).afirst():
            state["user"] = user
            return user
    await matcher.finish()


# 检查是否为班级群
async def class_table_depends(state: T_State, matcher: Matcher, event: GroupMessageEvent):
    if class_table := await ClassTable.objects.filter(group_id=event.group_id).afirst():
        state["class_table"] = class_table
        return class_table
    else:
        await matcher.finish()


# 教师或班干部
async def teacher_or_class_cadre_depends(state: T_State, matcher: Matcher, event: Event):
    if teacher := await Teacher.objects.filter(qq=event.get_user_id()).afirst():
        state["teacher"] = teacher
        return teacher
    elif student := await Student.objects.filter(qq=event.get_user_id()).afirst():
        if student.position in ClassCadre.to_list():
            state["student"] = student
            return student
    await matcher.finish()


CLASS_CADRE: Student

USER: User = Depends(user_depends)
STUDENT: Student = Depends(student_depends)
TEACHER: Teacher = Depends(teacher_depends)
CLASS_TABLE: ClassTable = Depends(class_table_depends)
TEACHER_OR_CLASS_CADRE: User = Depends(teacher_or_class_cadre_depends)


__all__ = [
    "User",
    "USER",
    "STUDENT",
    "TEACHER",
    "CLASS_TABLE",
    "CLASS_CADRE",
    "TEACHER_OR_CLASS_CADRE",
]
