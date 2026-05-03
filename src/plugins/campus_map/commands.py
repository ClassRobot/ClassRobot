from utils import tip
from utils.config import priority, comp_config
from utils.helper import Param, Helper, HelperScope, ParamMode
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, on_alconna

campus_map_cmd = on_alconna(
    Alconna(
        "校园地图",
        Args["position", MultiVar(str, "+"), Field(completion=tip("您想知道学校哪个地方的位置"))],
    ),
    priority=priority,
    block=True,
    comp_config=comp_config,
)


__helpers__ = [
    Helper(
        command="校园地图",
        description="查询学校某个楼的位置。",
        ai_description="当用户需要去什么地方，查询什么位置时调用这个命令来帮助用户，而不是AI去捏造一些不存在的地方或路线。",
        params=[Param(name="position", mode=ParamMode.ONE_OR_MORE, description="您想知道学校哪个地方的位置")],
        scopes={HelperScope.public},
    )
]
