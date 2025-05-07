from nonebot.typing import T_State
from nonebot.adapters import Bot, Event
from utils.session import session as get_session
from utils.models.depends import get_user_depends
from nonebot_plugin_alconna import Alconna, Arparma
from nonebot_plugin_alconna import UniMessage, get_target
from nonebot_plugin_alconna import Extension as BaseExtension


class AdminExtension(BaseExtension):
    """管理员扩展"""

    state: T_State | None = None
    """用户"""

    @property
    def priority(self) -> int:
        return 1

    @property
    def id(self):
        return "superuser"

    async def permission_check(self, bot: Bot, event: Event, command: Alconna) -> bool:
        assert self.state
        target = get_target(event, bot)
        assert (session := await get_session(target, event))
        user = await get_user_depends(session, self.state)
        return bool(user and user.is_admin)

    async def message_provider(
        self, event: Event, state: T_State, bot: Bot, use_origin: bool = False
    ) -> UniMessage | None:
        """提供消息对象以便 Alconna 进行处理。"""
        self.state = state
        return None
