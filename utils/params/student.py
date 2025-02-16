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


def get_columns_chinese(ignore: list[str] | None = None) -> dict:
    """获取中文列名"""
    ignore = ignore or []
    return {key: values[0] for key, values in columns.items() if key not in ignore}


columns_chinese = get_columns_chinese()


def get_column_key(value: str) -> str:
    """获取列的key"""
    for key, values in columns.items():
        if value in values:
            return key
    return value


def is_user_key(value: str) -> bool:
    """是否是用户的key"""
    return value in ["email", "phone", "username"]


def is_student_key(value: str) -> bool:
    """是否是学生的key"""
    return value in ["role", "name"]


def is_student_extra_key(value: str) -> bool:
    """是否是学生额外信息的key"""
    return value in [
        "sex",
        "dormitory",
        "student_code",
        "family_contact",
        "political_status",
    ]
