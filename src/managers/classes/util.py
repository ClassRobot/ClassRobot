student_column_renames: dict[str, list[str]] = {
    "name": ["姓名", "名字"],
    "student_id": ["学号"],
    "school": ["学校", "学校名称", "大学"],
    "college": ["学院", "二级学院", "院系", "学院名称", "院部"],
    "classes": ["班级", "班级名称"],
    "sex": ["性别"],
    "nation": ["民族", "国籍"],
    "phone": ["手机号", "电话", "联系方式"],
    "political_status": ["政治面貌", "政治状态"],
    "family_address": ["家庭住址", "家庭地址", "联系地址", "联系住址"],
    "birthday": ["出生日期", "出生年月"],
    "major": ["专业", "专业名称", "录取专业"],
}
student_column_required = {
    "name",
    "student_id",
    "school",
    "college",
    "classes",
}


def rename(name: str) -> str:
    for key in student_column_renames:
        if isinstance(student_column_renames[key], str) and name == student_column_renames[key]:
            return key
        elif isinstance(student_column_renames[key], list) and name in student_column_renames[key]:
            return key
    return name
