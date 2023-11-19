from nonebot import on_command
from utils.auth import UserExtension
from nonebot_plugin_alconna import on_alconna

create_user_cmd = on_command("创建用户", aliases={"成为用户"}, block=True)
show_user_cmd = on_command("用户信息", aliases={"我的信息"}, block=True)
bind_token_cmd = on_command("bind_token=", block=True)
bind_user_cmd = on_alconna(
    "绑定用户",
    aliases={"绑定我的信息", "绑定信息", "绑定平台"},
    block=True,
    extensions=[UserExtension(True)],
)
