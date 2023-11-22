from nonebot import on_command
from utils.typings import UserType
from utils.auth import UserExtension
from src.others.helper import add_help
from nonebot_plugin_alconna import on_alconna
from src.others.helper.typings import Helper, ExampleMessage

create_user_cmd = on_command("创建用户", aliases={"成为用户"}, block=True)
show_user_cmd = on_command("用户信息", aliases={"我的信息"}, block=True)
bind_token_cmd = on_command("bind_token=", block=True)
bind_user_cmd = on_alconna(
    "绑定用户",
    aliases={"绑定我的信息", "绑定信息", "绑定平台"},
    block=True,
    extensions=[UserExtension(True)],
)


add_help(
    Helper(
        command="创建用户",
        description="用于创建用户",
        usage="创建用户",
        example=[
            ExampleMessage(user_type=UserType.USER, message="创建用户"),
            ExampleMessage(user_type="bot", message="创建用户成功"),
        ],
        aliases={"成为用户"},
        category={"用户"},
    ),
    Helper(
        command="用户信息",
        description="用于查询用户信息",
        usage="用户信息",
        example=[
            ExampleMessage(user_type=UserType.USER, message="用户信息"),
            ExampleMessage(user_type="bot", message="您的用户id"),
        ],
        aliases={"我的信息"},
        category={"用户"},
    ),
    Helper(
        command="绑定用户",
        description="用于绑定用户信息",
        usage="绑定用户 [用户id或@用户]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="绑定用户"),
            ExampleMessage(
                user_type="bot", message="将以下信息复制到需要绑定的平台\nbind_token=123456"
            ),
        ],
        aliases={"绑定我的信息", "绑定信息", "绑定平台"},
        category={"用户"},
    ),
)
