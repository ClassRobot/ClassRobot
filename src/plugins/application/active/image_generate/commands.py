from src.shared import tip
from src.platform.config import priority, comp_config
from src.platform.commands import CommandBinding, on_agent_command
from src.platform.helper import HelperScope, UserRole
from nonebot_plugin_alconna import Args, Text, Field, Image, Alconna, MultiVar

image_generate_cmd = on_agent_command(
    Alconna(
        "图片生成",
        Args["values", MultiVar(Text | Image, "+"), Field(completion=tip("输入图片或文字"))],
    ),
    aliases={"生成图片", "图生图", "图生成"},
    binding=CommandBinding(
        description="使用 AI 来图生图或者根据文字生成图片。",
        ai_description="该命令适合处理图生图、文生图、图片加文字修改等需求。例如：图生成 一只猫咪；图生成 [图片] 给这个猫咪穿衣服。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="medium",
        agent_callable=False,
        param_labels={"values": "图片加文字需求"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [image_generate_cmd.__helper__]
