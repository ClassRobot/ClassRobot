from nonebot_plugin_alconna import Args, Field


def check_name(name: str) -> str | None:
    if not name.isdigit():
        return name


def name_not_numeric_args(
    key: str = "name",
    prompt: str = "请输入名称",
    tips: str = "名称不能为纯数字",
) -> Args:
    return Args[
        key,
        check_name,
        Field(completion=lambda: prompt, unmatch_tips=lambda x: tips.format(x)),
    ]


class NameNotNumeric:
    @staticmethod
    def student_name(key: str = "student_name"):
        """输入学生昵称，不能为数字"""
        return name_not_numeric_args(key, "请输入学生昵称", "学生昵称不能为纯数字")

    @staticmethod
    def class_name(key: str = "class_name"):
        """输入班级名称，不能为数字"""
        return name_not_numeric_args(key, "请输入班级名称", "班级名称不能为纯数字")

    @staticmethod
    def teacher_name(key: str = "teacher_name"):
        """输入教师昵称，不能为数字"""
        return name_not_numeric_args(key, "请输入教师昵称", "教师昵称不能为纯数字")
