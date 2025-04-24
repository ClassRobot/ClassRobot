from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import Alconna
from nonebot_plugin_alconna import get_target
from utils.models.depends import get_user_depends
from nonebot_plugin_alconna import Extension as BaseExtension


class AdminExtension(BaseExtension):
    """管理员扩展"""

    @property
    def priority(self) -> int:
        return 1

    @property
    def id(self):
        return "admin_extension"

    def permission_check(self, bot: Bot, event: Event, command: Alconna):
        target = get_target(event, bot)

        return True
