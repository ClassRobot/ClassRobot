from typing import Iterable

from pandas import DataFrame
from utils.models import Student

columns = {
    "name": ["姓名"],
    "role": ["角色", "职位", "班干部"],
    "phone": ["电话", "手机号", "联系方式"],
    "user_id": ["用户ID", "用户编号"],
    "email": ["邮箱", "电子邮箱"],
    "classes": ["班级", "班级名称"],
    "sex": ["性别"],
    "dormitory": ["宿舍", "寝室"],
    "student_code": ["学号", "学生编号"],
    "family_contact": ["家庭联系方式", "家庭联系电话"],
    "political_status": ["政治面貌"],
}

default_display_columns = [
    "user_id",
    "student_code",
    "name",
    "role",
    "phone",
    "email",
    "classes",
]
columns_chinese = {key: values[0] for key, values in columns.items() if key not in []}


def get_display_columns(items: list[str]) -> list[str]:
    """获取要显示的列"""
    display_columns = ["user_id", "student_code", "name", "classes"]
    length = len(display_columns)
    for item in items:
        for key, values in columns.items():
            if item in values and key not in display_columns:
                display_columns.append(key)
    if len(display_columns) == length:
        return default_display_columns.copy()
    return display_columns


def student_to_dict(student: Student) -> dict:
    """将学生对象转成字典"""
    data = {
        "name": student.name,
        "role": student.role,
        "phone": student.user.phone,
        "user_id": student.user.id,
        "email": student.user.email,
        "classes": student.classes.name,
    }
    for bind in student.user.binds:
        data[bind.platform_id] = bind.account_id
    if student.extra:
        data.update(
            {
                "sex": student.extra.sex,
                "dormitory": student.extra.dormitory,
                "student_code": student.extra.student_code,
                "family_contact": student.extra.family_contact,
                "political_status": student.extra.political_status,
            }
        )
    return data


def to_df(students: Iterable[Student]) -> DataFrame:
    """取出指定字段转成 DataFrame"""
    df = DataFrame(student_to_dict(student) for student in students)
    # 补全columns，不存在的用None填充
    for key in columns:
        if key not in df:
            df[key] = None
    return df
