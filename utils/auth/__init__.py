from typing import List, Union, Optional

from nonebot.params import Depends
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from sqlalchemy import ScalarResult
from nonebot_plugin_orm import get_session, select, first, one_or_none
from nonebot.adapters import Event

from utils.adapter.event import GroupMessageEvent
from utils.models import Student, Teacher, ClassTable

from .config import ClassCadre

User = Union[Teacher, Student]


async def get_student(qq: Union[str, int]) -> Optional[Student]:
    async with get_session() as session:
        result: ScalarResult[Student] = await session.scalars(
            select(Student).where(Student.QQ == qq)
        )
        if student := result.first():
            return student
        return None


async def get_teacher(qq: Union[str, int]) -> Optional[Teacher]:
    async with get_session() as session:
        result: ScalarResult[Teacher] = await session.scalars(
            select(Teacher).where(Teacher.qq == qq)
        )
        if teacher := result.first():
            return teacher
        return None


async def get_class_table(group_id: Union[str, int]) -> Optional[ClassTable]:
    async with get_session() as session:
        result: ScalarResult[ClassTable] = await session.scalars(
            select(ClassTable).where(ClassTable.group_id == group_id)
        )
        if class_table := result.first():
            return class_table
        return None

async def get_teacher_class(teacher_id: int | str):
    async with get_session() as session:
        result = await session.scalars(
            select(ClassTable).where(ClassTable.teacher == Teacher.id)
        )

def is_class_cadre(student: Student, cadres: str | list[str] | None = None) -> bool:
    """是否为班干部

    Args:
        student (Student): 学生
        cadres (str | list[str] | None, optional): 自定义干部. Defaults to None.
            比如期望查询某一位干部，可以通过这个参数来指定

    Returns:
        bool: 是否为干部
    """
    if cadres is None:
        return student.position in ClassCadre.to_list()
    elif isinstance(cadres, str):
        return student.position == cadres
    elif isinstance(cadres, list):
        return student.position in cadres


# 学生身份
async def student_depends(state: T_State, matcher: Matcher, event: Event):
    if student := await get_student(event.get_user_id()):
        state["student"] = student
        return student
    else:
        await matcher.finish()


# 班干部身份
def CLASS_CADRE(cadres: Optional[List[str]] = None):  # type: ignore
    """是否为班干部

    Args:
        cadres (Optional[List[str]], optional): 选择哪些班干部. Defaults to None.
            如果为None表示全部
            如果为str表示单个
            如果为list表示几位
    """

    async def _(state: T_State, matcher: Matcher, event: Event) -> Student:
        if student := await get_student(event.get_user_id()):
            if is_class_cadre(student, cadres):
                state["student"] = student
                return student
        await matcher.finish()

    return Depends(_)


# 教师身份
async def teacher_depends(state: T_State, matcher: Matcher, event: Event) -> Student:
    if teacher := await get_student(event.get_user_id()):
        state["teacher"] = teacher
        return teacher
    else:
        await matcher.finish()


# 是否为系统中的任何类型的用户
async def user_depends(state: T_State, matcher: Matcher, event: Event) -> User:
    user_id = event.get_user_id()
    for get in list((get_student, get_teacher)):
        if user := await get(user_id):
            state["user"] = user
            return user
    await matcher.finish()


# 检查是否为班级群
async def class_table_depends(
    state: T_State, matcher: Matcher, event: GroupMessageEvent
):
    if class_table := await get_class_table(event.group_id):
        state["class_table"] = class_table
        return class_table
    else:
        await matcher.finish()


# 教师或班干部
async def teacher_or_class_cadre_depends(
    state: T_State, matcher: Matcher, event: Event
):
    user_id = event.get_user_id()
    if teacher := await get_teacher(user_id):
        state["teacher"] = teacher
        return teacher
    elif student := await get_student(user_id):
        if is_class_cadre(student):
            state["student"] = student
            return student
    await matcher.finish()


# 该教师所管理的班级群
async def class_table_of_teacher_depends(
    state: T_State, matcher: Matcher, event: GroupMessageEvent
):
    user_id = event.get_user_id()
    group_id = event.group_id
    if teacher := await get_teacher(user_id):
        if class_table := await get_class_table(group_id):
            state["class_table"] = class_table
            return class_table
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
