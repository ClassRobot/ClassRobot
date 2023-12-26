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
        return name_not_numeric_args(key, "请输入学生昵称", "学生昵称不能为纯数字")

    @staticmethod
    def class_name(key: str = "class_name"):
        return name_not_numeric_args(key, "请输入班级名称", "班级名称不能为纯数字")

    @staticmethod
    def teacher_name(key: str = "teacher_name"):
        return name_not_numeric_args(key, "请输入教师昵称", "教师昵称不能为纯数字")


class NameOrId:
    @staticmethod
    def student_name(key: str = "student_name_or_id"):
        return Args[key, int | str, Field(completion=lambda: "请输入学生昵称或学生id")]

    @staticmethod
    def class_name(key: str = "class_name_or_id"):
        return Args[key, int | str, Field(completion=lambda: "请输入班级名称或班级id")]

    @staticmethod
    def teacher_name(key: str = "teacher_name_or_id"):
        return Args[key, int | str, Field(completion=lambda: "请输入教师昵称或教师id")]
