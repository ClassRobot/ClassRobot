from nonebot import on_command
from src.platform.config import priority, comp_config
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar
from src.platform.commands import CommandBinding, on_agent_command

notice_cmd = on_command(
    "创建通知",
    aliases={"定时", "转发"},
    priority=priority,
    block=True,
)
query_notice_cmd = on_agent_command(
    Alconna("查询通知"),
    binding=CommandBinding(
        description="查询自己发布的通知。",
        helper_visible=False,
        agent_callable=False,
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
)
delete_notice_cmd = on_agent_command(
    Alconna(
        "删除通知",
        Args["notice_id", MultiVar(str, "+"), Field(completion=lambda: "请输入通知ID")],
    ),
    binding=CommandBinding(
        description="删除自己发布的通知。",
        helper_visible=False,
        agent_callable=False,
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
