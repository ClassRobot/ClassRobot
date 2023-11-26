from utils.config import comp_config
from utils.auth.extension import TeacherOrStudentExtension
from nonebot_plugin_alconna import Args, Field, Image, Alconna, MultiVar, on_alconna

# 添加任务
add_task_cmd = on_alconna(
    Alconna(
        "添加任务",
        Args["task_name", str, Field(completion=lambda: "请输入任务名称")],
    ),
    aliases={"增加任务"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherOrStudentExtension],
)

# 提交任务
submit_task_cmd = on_alconna(
    Alconna(
        "提交任务",
        Args["task_name", str, Field(completion=lambda: "这个任务叫什么呢？")],
        Args["task_image", Image, Field(completion=lambda: "请给截图给我吧")],
    ),
    block=True,
    comp_config=comp_config,
    extensions=[TeacherOrStudentExtension],
)

# 查询任务
search_task_cmd = on_alconna(
    Alconna(
        "查询任务",
        Args["task_name", MultiVar(str | int, flag="*")],
    ),
    aliases={"查看任务"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherOrStudentExtension],
)

# 删除任务
del_task_cmd = on_alconna(
    Alconna(
        "删除任务",
        Args["task_name", str, Field(completion=lambda: "请输入任务名称")],
    ),
    aliases={"移除任务"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherOrStudentExtension],
)
