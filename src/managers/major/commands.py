from utils.config import comp_config
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
        "查看专业",
        Args["college_name", str, Field(completion=lambda: "请输入院系名称")],
    ),
    aliases={"查询专业"},
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
