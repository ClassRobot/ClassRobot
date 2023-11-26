from utils.typings import UserType
from utils.config import comp_config
from src.others.helper import add_help
from utils.auth import TeacherExtension
from src.others.helper.typings import Helper, ExampleMessage
from nonebot_plugin_alconna import At, Args, Field, Alconna, on_alconna

add_teacher_cmd = on_alconna(
    Alconna(
        "添加教师",
        Args["name", str, Field(completion=lambda: "请输入教师姓名")],
        Args["phone", int, Field(completion=lambda: "请输入教师手机号码")],
        Args["user_id_or_at", [int, At], Field(completion=lambda: "输入用户id或@教师")],
    ),
    aliases={"添加老师"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

del_teacher_cmd = on_alconna(
    Alconna(
        "删除教师",
        Args["user_id", [int, At], Field(completion=lambda: "输入用户id或@教师")],
    ),
    aliases={"删除老师"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)


add_help(
    Helper(
        command="添加教师",
        description="教师或管理员来添加教师",
        usage="添加教师 [教师姓名] [教师手机号码] [用户id或@教师]",
        example=[
            ExampleMessage(
                user_type=UserType.TEACHER, message="添加教师 张三 12345678901 123456"
            ),
            ExampleMessage(user_type="bot", message="张三 添加成功"),
        ],
        aliases={"添加老师"},
        category={"添加", "教师", "老师"},
    ),
    Helper(
        command="删除教师",
        description="管理员删除教师",
        usage="删除教师 [用户id或@教师]",
        example=[
            ExampleMessage(user_type=UserType.ADMIN, message="删除教师 123456"),
            ExampleMessage(user_type="bot", message="123456 删除成功"),
        ],
        aliases={"删除老师"},
        category={"删除", "教师", "老师"},
    ),
)
