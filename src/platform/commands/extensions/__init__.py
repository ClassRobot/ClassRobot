from nonebot.typing import T_State
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import Alconna
from src.platform.session import session as get_session
from src.platform.session.depends import get_user_depends
from nonebot_plugin_alconna import UniMessage, get_target, Extension as BaseExtension


class AdminExtension(BaseExtension):
    """管理员扩展"""

    state: T_State | None = None
    """用户"""

    @property
    def priority(self) -> int:
        """返回扩展优先级。"""
        return 1

    @property
    def id(self):
        """返回扩展标识。"""
        return "superuser"

    async def permission_check(self, bot: Bot, event: Event, command: Alconna) -> bool:
        """检查权限。

        参数:
            bot (Bot): 当前机器人实例。
            event (Event): 当前事件对象。
            command (Alconna): command。

        返回:
            bool: 表示是否成功。
        """
        assert self.state
        target = get_target(event, bot)
        assert (session := await get_session(target, event))
        user = await get_user_depends(session, self.state)
        return bool(user and user.is_admin)

    async def message_provider(
        self, event: Event, state: T_State, bot: Bot, use_origin: bool = False
    ) -> UniMessage | None:
        """处理消息provider相关逻辑。

        参数:
            event (Event): 当前事件对象。
            state (T_State): state。
            bot (Bot): 当前机器人实例。
            use_origin (bool): useorigin。

        返回:
            UniMessage | None: 返回处理结果。
        """
        self.state = state
        return None
