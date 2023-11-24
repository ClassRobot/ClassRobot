from utils.typings import UserType
from utils.config import comp_config
from src.others.helper import add_help
from utils.auth.extension import TeacherExtension
from src.others.helper.typings import Helper, ExampleMessage
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

add_class_table_cmd = on_alconna(
    Alconna(
        "添加班级",
        Args["name", str, Field(completion=lambda: "请输入班级名称")],
        Args["major_name", str, Field(completion=lambda: "请输入专业名称")],
    ),
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

del_class_table_cmd = on_alconna(
    Alconna(
        "删除班级",
        Args["name", str, Field(completion=lambda: "请输入班级名称")],
    ),
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

bind_class_table_cmd = on_alconna(
    Alconna(
        "绑定班级",
        Args["name", str, Field(completion=lambda: "请输入班级名称")],
    ),
    aliases={"绑定班级群"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

show_class_table_cmd = on_alconna(
    "查询班级",
    aliases={"查看班级"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

add_help(
    Helper(
        command="添加班级",
        description="教师身份来添加班级，默认会将命令执行的群作为班级群",
        usage="添加班级 [班级名称] [专业名称]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="添加班级 人工智能 信息工程"),
            ExampleMessage(user_type="bot", message="[人工智能] 添加成功"),
        ],
        category={"添加", "班级"},
    ),
    Helper(
        command="删除班级",
        description="删除教师自己创建的班级",
        usage="删除班级 [班级名称]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="删除班级 人工智能"),
            ExampleMessage(user_type="bot", message="[人工智能] 删除成功"),
        ],
        category={"删除", "班级"},
    ),
    Helper(
        command="绑定班级",
        description="将当前的群与班级进行绑定",
        usage="绑定班级 [班级名称]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="绑定班级 人工智能"),
            ExampleMessage(user_type="bot", message="[人工智能] 绑定成功"),
        ],
        aliases={"绑定班级群"},
        category={"绑定", "班级"},
    ),
    Helper(
        command="查询班级",
        description="用于插件教师自己添加的班级",
        usage="查询班级",
        example=[
            ExampleMessage(user_type=UserType.USER, message="查询班级"),
            ExampleMessage(user_type="bot", message="您所创建的班级如下:\n1. 人工智能"),
        ],
        aliases={"查看班级"},
        category={"查询", "班级"},
    ),
)
