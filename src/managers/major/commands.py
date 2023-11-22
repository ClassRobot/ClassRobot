from utils.typings import UserType
from utils.config import comp_config
from src.others.helper import add_help
from src.others.helper.typings import Helper, ExampleMessage
from utils.auth.extension import UserExtension, AdminExtension
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

add_major_cmd = on_alconna(
    Alconna(
        "添加专业",
        Args["name", str, Field(completion=lambda: "请输入专业名称")],
        Args["college_name", str, Field(completion=lambda: "请输入院系名称")],
    ),
    comp_config=comp_config,
    block=True,
    extensions=[AdminExtension],
)

show_major_cmd = on_alconna(
    Alconna(
        "查询专业",
        Args["college_name", str, Field(completion=lambda: "请输入院系名称")],
    ),
    aliases={"查看专业"},
    comp_config=comp_config,
    block=True,
    extensions=[UserExtension],
)


del_major_cmd = on_alconna(
    Alconna(
        "删除专业",
        Args["name", str, Field(completion=lambda: "请输入专业名称")],
    ),
    comp_config=comp_config,
    block=True,
    extensions=[AdminExtension],
)


add_help(
    Helper(
        command="添加专业",
        description="用于添加专业",
        usage="添加专业 [专业名称] [院系名称]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="添加专业 人工智能 信息工程"),
            ExampleMessage(user_type="bot", message="人工智能 添加成功"),
        ],
        aliases={"添加专业"},
        category={"添加", "专业"},
    ),
    Helper(
        command="删除专业",
        description="用于删除专业",
        usage="删除专业 [专业名称]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="删除专业 人工智能"),
            ExampleMessage(user_type="bot", message="人工智能 删除成功"),
        ],
        aliases={"删除专业"},
        category={"删除", "专业"},
    ),
    Helper(
        command="查询专业",
        description="用于查询专业",
        usage="查询专业 [院系名称]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="查询专业 信息工程"),
            ExampleMessage(user_type="bot", message="信息工程 已存在的专业如下\n1.人工智能"),
        ],
        aliases={"查询专业"},
        category={"查询", "专业"},
    ),
)
