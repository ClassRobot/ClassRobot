from utils.config import priority, comp_config
from utils.helper import Param, Helper, UserRole
from nonebot_plugin_alconna import Args, Field, Image, Alconna, MultiVar, on_alconna

text_gen_cmd = on_alconna(
    Alconna(
        "文本创作",
        Args[
            "values",
            MultiVar(str | Image, "+"),
            Field(completion=lambda: "是要生成什么样的内容呢?"),
        ],
    ),
    aliases={"生成文本"},
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [
    Helper(
        command="文本创作",
        aliases={"生成文本"},
        description="当需要AI生成长内容时请务必使用此命令来生成。",
        params=[Param(name="内容要求", description="文本内容")],
        roles={UserRole.user},
    )
]
