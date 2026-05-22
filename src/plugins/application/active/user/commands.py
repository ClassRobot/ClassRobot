from src.shared import tip
from nonebot import on_command
from src.platform.config import priority, comp_config
from src.platform.commands import CommandBinding, on_agent_command
from src.platform.helper import Context, HelperScope, UserRole
from nonebot_plugin_alconna import Args, Field, Alconna, CommandMeta

self_info_cmd = on_agent_command(
    Alconna(
        "我的信息",
        meta=CommandMeta(description="查看自己的账号信息、当前角色、是否为管理员、是否为教师或学生"),
    ),
    aliases={"个人信息", "用户信息"},
    binding=CommandBinding(
        ai_description="当用户询问“我是谁”“我的身份是什么”“我是不是管理员/教师/学生/班干部”“我有哪些权限/角色”时，优先调用该命令查询当前账号信息，不要要求用户补充QQ群身份。",
        roles={UserRole.user},
        scopes={HelperScope.user},
    ),
    priority=priority,
    block=True,
)

bind_user_cmd = on_agent_command(
    Alconna(
        "绑定用户",
        meta=CommandMeta(description="用于在不同平台之间绑定同一个用户信息"),
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
            Field(
                completion=tip(
                    "可以选择注销**用户**，**教师**或**学生**，一旦注销将无法恢复，相关数据也会被删除，请慎重！"
                )
            ),
        ],
        meta=CommandMeta(description="注销当前用户，删除相关数据"),
    ),
    aliases={"删除账号", "账号注销"},
    binding=CommandBinding(
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


__helpers__ = [
    self_info_cmd.__helper__,
    bind_user_cmd.__helper__,
    logout_cmd.__helper__,
]
