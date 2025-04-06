from typing import Annotated

from utils.models import Student
from nonebot.params import Depends
from nonebot.matcher import Matcher
from pandas import DataFrame, concat
from utils.models.depends import StudentDepends, TeacherDepends

from .util import students_to_df


async def get_student_classmates(
    matcher: Matcher, student: StudentDepends
) -> set[Student]:
    name = "_student_classmates"
    if name in matcher.state:
        return matcher.state[name]
    elif student:
        matcher.state[name] = set(await student.get_classmates())
        return matcher.state[name]
    return set()


StudentClassmates = Annotated[set[Student], Depends(get_student_classmates)]


async def get_teacher_students(
    matcher: Matcher, teacher: TeacherDepends
) -> set[Student]:
    name = "_teacher_students"
    if name in matcher.state:
        return matcher.state[name]
    elif teacher:
        matcher.state[name] = set(await teacher.get_students())
        return matcher.state[name]
    return set()


TeacherStudents = Annotated[set[Student], Depends(get_teacher_students)]


async def get_students(
    classmates: StudentClassmates, students: TeacherStudents
) -> set[Student]:
    return students | classmates


UserStudents = Annotated[set[Student], Depends(get_students)]


async def find_students(students: UserStudents, items: list[str]) -> DataFrame:
    students_df = students_to_df(students)
    # 如果items内容带有`.`的方式搜索，则是从左至右满足条件的匹配，比如`1班.张三`就会先搜索1班再在1班中搜索名字为张三的学生
    # 搜索不考虑列名，只要有一个字段满足条件即可
    results = []
    for item in items:
        result = students_df.copy()
        item_split = [i.strip() for i in item.split(".") if i.strip()]
        for i in item_split:
            result = result[result.astype(str).eq(i).any(axis=1)]
        if not result.empty:
            results.append(result)

    if not results:
        return DataFrame()

    # 将结果合并
    final_result = concat(results, ignore_index=True).drop_duplicates()
    return final_result


FindStudents = Annotated[DataFrame, Depends(find_students)]
