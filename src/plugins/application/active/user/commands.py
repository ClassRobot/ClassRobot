from src.shared import tip
from nonebot import on_command
from src.platform.config import priority, comp_config
from src.platform.helper import Context, UserRole, HelperScope
from src.platform.commands import CommandBinding, on_agent_command
from nonebot_plugin_alconna import Args, Field, Alconna, CommandMeta

self_info_cmd = on_agent_command(
    Alconna(
        "我的信息",
        meta=CommandMeta(description="查看自己的账号信息、当前角色、是否为管理员、是否为教师或学生"),
    ),
    aliases={"个人信息", "用户信息"},
    binding=CommandBinding(
        description="查看当前账号、绑定身份、角色和权限信息。",
        roles={UserRole.user},
        scopes={HelperScope.user},
    ),
    priority=priority,
    block=True,
)

bind_user_cmd = on_agent_command(
    Alconna(
        "绑定用户",
        meta=CommandMeta(description="把不同平台账号绑定到同一个系统用户。"),
    ),
    aliases={"绑定平台", "绑定", "换绑平台", "关联平台"},
    binding=CommandBinding(
        roles={UserRole.user},
        scopes={HelperScope.user},
        execution_mode="interactive",
        examples=[
            Context(rote="用户A", content="绑定用户"),
            Context(rote="机器人", content="需要绑定平台请在5分钟内将以下token粘贴到指定平台发送:\ntoken=xxxxxx"),
            Context(rote="用户B", content="token=xxxxxx"),
            Context(rote="用户B", content="此时用户B查询的用户信息实际上是用户A的信息"),
        ],
    ),
    priority=priority,
    block=True,
)

logout_cmd = on_agent_command(
    Alconna(
        "注销",
        Args[
            "role",
            str,
            Field(completion=tip("可以选择注销**用户**，**教师**或**学生**，一旦注销将无法恢复，相关数据也会被删除，请慎重！")),
        ],
        meta=CommandMeta(description="注销当前用户，删除相关数据"),
    ),
    aliases={"删除账号", "账号注销"},
    binding=CommandBinding(
        description="注销当前用户、教师或学生身份；相关数据会被删除。",
        roles={UserRole.user},
        scopes={HelperScope.user},
        risk_level="high",
        agent_callable=True,
        execution_mode="interactive",
        param_labels={"role": "角色"},
    ),
    priority=priority,
    comp_config=comp_config,
    skip_for_unmatch=False,
    block=True,
)


token_cmd = on_command("token", priority=priority, block=True)
