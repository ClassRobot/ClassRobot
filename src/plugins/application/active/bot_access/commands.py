from src.shared import tip
from src.core.auth import UserRole
from src.platform.helper import Context, HelperScope
from src.platform.config import priority, comp_config
from src.platform.commands import CommandBinding, on_agent_command
from nonebot_plugin_alconna import Args, Field, Alconna, CommandMeta

bot_access_cmd = on_agent_command(
    Alconna(
        "接入机器人",
        Args[
            "platform",
            str,
            Field(completion=tip("目前支持：微信。后续可扩展 qqclaw 等平台。")),
        ],
        meta=CommandMeta(description="扫码接入自己的平台机器人账号，例如微信机器人。"),
    ),
    binding=CommandBinding(
        description="通过扫码把自己的微信机器人接入系统，接入后会随系统启动自动上线。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        execution_mode="interactive",
        agent_callable=False,
        param_labels={"platform": "平台"},
        param_descriptions={"platform": "机器人接入平台，当前支持“微信”。"},
        examples=[
            Context(rote="用户", content="接入机器人 微信"),
            Context(rote="机器人", content="发送微信机器人接入二维码，用户扫码后完成接入。"),
        ],
        tags={"bot", "platform", "wxclaw"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
