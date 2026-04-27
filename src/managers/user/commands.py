from utils import tip
from nonebot import on_command
from utils.config import priority, comp_config
from utils.helper import Helper, Context, UserRole
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

self_info_cmd = on_alconna(Alconna("我的信息"), aliases={"个人信息", "用户信息"}, priority=priority, block=True)

bind_user_cmd = on_alconna(
    Alconna("绑定用户"),
    aliases={"绑定平台", "绑定", "换绑平台", "关联平台"},
    priority=priority,
    block=True,
)

logout_cmd = on_alconna(
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
    ),
    aliases={"删除账号", "账号注销"},
    priority=priority,
    comp_config=comp_config,
    skip_for_unmatch=False,
    block=True,
)


token_cmd = on_command("token", priority=priority, block=True)


__helpers__ = [
    Helper(
        command="我的信息",
        description="查看自己的信息,是否为教师或学生",
        aliases={"个人信息", "用户信息"},
    ),
    Helper(
        command="绑定用户",
        description="用于在不同平台之间绑定同一个用户信息，执行命令后会生成一个token，将token发送给指定平台的机器人即可完成绑定",
        aliases={"绑定平台", "绑定", "换绑平台", "关联平台"},
        example=[
            Context(
                rote="用户A",
                content="绑定用户",
            ),
            Context(
                rote="机器人",
                content="需要绑定平台请在5分钟内将以下token粘贴到指定平台发送:\ntoken=xxxxxx",
            ),
            Context(
                rote="用户B",
                content="token=xxxxxx",
            ),
            Context(
                rote="用户B",
                content="此时用户B查询的用户信息实际上是用户A的信息",
            ),
        ],
    ),
    Helper(
        command="注销",
        description="注销当前用户，删除相关数据",
        aliases={"删除账号", "账号注销"},
        roles={UserRole.user, UserRole.teacher, UserRole.student},
    ),
]
