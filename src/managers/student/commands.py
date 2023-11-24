from utils.config import comp_config
from utils.auth.extension import TeacherExtension
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

add_student_cmd = on_alconna(
    Alconna(
        "添加学生",
        Args["name", str, Field(completion=lambda: "请输入学生姓名")],
        Args["class_name", str, Field(completion=lambda: "请输入添加到的班级名称")],
        Args["user_id", int, Field(completion=lambda: "请输入这位学生的用户id")],
    ),
    aliases={"增加学生"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

batch_add_student_cmd = on_alconna(
    Alconna(
        "导入学生",
        Args["class_name", str, Field(completion=lambda: "请输入添加到的班级名称")],
        Args["url", str, Field(completion=lambda: "请发送腾讯文档链接")],
    ),
    aliases={"批量添加学生"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)
