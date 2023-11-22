from utils.typings import UserType
from utils.config import comp_config
from src.others.helper import add_help
from utils.auth import UserExtension, AdminExtension
from src.others.helper.typings import Helper, ExampleMessage
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

add_college_cmd = on_alconna(
    Alconna(
        "添加院系",
        Args["name", str, Field(completion=lambda: "请输入院系名称")],
    ),
    aliases={"添加学院"},
    block=True,
    comp_config=comp_config,
    extensions=[AdminExtension],
)
show_college_cmd = on_alconna(
    "查询院系",
    aliases={"查询学院", "查看学院", "查看院系"},
    block=True,
    comp_config=comp_config,
    extensions=[UserExtension],
)
del_college_cmd = on_alconna(
    Alconna(
        "删除院系",
        Args["name", str, Field(completion=lambda: "请输入院系名称或id")],
    ),
    aliases={"删除学院"},
    block=True,
    comp_config=comp_config,
    extensions=[AdminExtension],
)


add_help(
    Helper(
        command="添加院系",
        description="用于添加院系，添加过后可以添加具体的专业",
        usage="添加院系 [院系名称]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="添加院系 信息工程"),
            ExampleMessage(user_type="bot", message="信息工程 添加成功"),
        ],
        aliases={"添加学院"},
        category={"添加", "院系", "学院"},
    ),
    Helper(
        command="删除院系",
        description="用于删除院系，删除过后该院系的专业也会被删除",
        usage="删除院系 [院系名称或id]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="删除院系 信息工程"),
            ExampleMessage(user_type="bot", message="信息工程 删除成功"),
        ],
        aliases={"删除院系"},
        category={"删除", "院系", "学院"},
    ),
    Helper(
        command="查询院系",
        description="用于查询已经添加的院系",
        usage="查询院系",
        example=[
            ExampleMessage(user_type=UserType.USER, message="查询院系"),
            ExampleMessage(user_type="bot", message="已经存在的学院如下\n1.信息工程"),
        ],
        aliases={"查看学院", "查询学院", "查看院系"},
        category={"查询", "院系", "学院"},
    ),
)
