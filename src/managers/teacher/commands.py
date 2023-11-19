from utils.config import comp_config
from utils.auth import TeacherExtension
from nonebot_plugin_alconna import At, Args, Field, Alconna, on_alconna

add_teacher_cmd = on_alconna(
    Alconna(
        "添加教师",
        Args["name", str, Field(completion=lambda: "请输入教师姓名")],
        Args["phone", int, Field(completion=lambda: "请输入教师手机号码")],
        Args["user_id", [str, At], Field(completion=lambda: "输入用户id或@教师")],
    ),
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)
