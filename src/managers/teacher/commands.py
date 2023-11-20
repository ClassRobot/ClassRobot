from utils.config import comp_config
from utils.auth import TeacherExtension
from nonebot_plugin_alconna import At, Args, Field, Alconna, on_alconna

add_teacher_cmd = on_alconna(
    Alconna(
        "添加教师",
        Args["name", str, Field(completion=lambda: "请输入教师姓名")],
        Args["phone", int, Field(completion=lambda: "请输入教师手机号码")],
        Args["user_id", [int, At], Field(completion=lambda: "输入用户id或@教师")],
    ),
    aliases={"添加老师"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

remove_teacher_cmd = on_alconna(
    Alconna(
        "删除教师",
        Args["user_id", [int, At], Field(completion=lambda: "输入用户id或@教师")],
    ),
    aliases={"删除老师"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)
