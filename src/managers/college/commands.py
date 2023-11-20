from utils.config import comp_config
from utils.auth import UserExtension, AdminExtension
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
    "查看院系",
    aliases={"查询学院", "查看学院", "查询院系"},
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
