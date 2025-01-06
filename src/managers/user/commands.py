from nonebot import on_command
from nonebot_plugin_alconna import on_alconna, Alconna

self_info_cmd = on_alconna(
    Alconna("个人信息"),
    aliases={"我的信息", "用户信息"},
)

bind_user_cmd = on_alconna(
    Alconna("绑定用户"),
    aliases={"绑定平台", "绑定", "换绑平台", "关联平台"},
)

token_cmd = on_command("token")
