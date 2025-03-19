from utils import tip
from utils.config import priority, comp_config
from utils.helper import Param, Helper, UserRole, ParamMode
from nonebot_plugin_alconna import Args, Text, Field, Image, Alconna, MultiVar, on_alconna

image_generate_cmd = on_alconna(
    Alconna(
        "图片生成",
        Args["values", MultiVar(Text | Image, "+"), Field(completion=tip("输入图片或文字"))],
    ),
    aliases={"生成图片", "图生图", "图生成"},
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [
    Helper(
        command="图片生成",
        aliases={"生成图片", "图生图", "图生成"},
        description="使用AI来图生图或者生成图片。",
        ai_description="该命令是处理用户图片，如图片生成图片，文字生成图片，图片加文字等需求。\n方式例如: \n图生成 一直猫咪 \n或者\n 图生成 [图片] 给这个猫咪穿衣服",
        params=[Param(name="图片加文字需求", mode=ParamMode.ONE_OR_MORE, description="输入图片或文字或者图片加文字需求")],
        roles={UserRole.user},
    )
]
