from src.platform.commands import CommandBinding, on_agent_command
from src.platform.config import priority
from src.platform.helper import HelperScope
from nonebot_plugin_alconna import Args, Alconna

help_cmd = on_agent_command(
    Alconna("help", Args["name?", str | None]),
    aliases={"帮助"},
    binding=CommandBinding(
        description="按当前身份查看自己可以使用的命令目录，或查询单个命令的详细帮助。",
        scopes={HelperScope.public},
        agent_callable=False,
    ),
    priority=priority,
    block=True,
)

__helpers__ = [help_cmd.__helper__]

__all__ = ["help_cmd", "__helpers__"]
