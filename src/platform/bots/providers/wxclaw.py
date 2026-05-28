from __future__ import annotations

from typing import Protocol, runtime_checkable

from nonebot import get_adapter
from src.models import PlatformBotAccount
from src.core.auth.crypto import decrypt_text
from nonebot.adapters.wxclaw import Bot as WxClawBot
from nonebot.adapters.wxclaw import Adapter as WxClawAdapter
from nonebot.adapters.wxclaw.config import WxClawAccountInfo
from nonebot.adapters.wxclaw.login import FIXED_BASE_URL, WxClawLoginResult


@runtime_checkable
class WxClawLoginResultLike(Protocol):
    """描述 wxclaw 扫码登录结果需要的最小字段。"""

    connected: bool
    account_id: str
    token: str
    base_url: str
    user_id: str
    message: str


class WxClawBotProvider:
    """封装项目侧对 `nonebot-adapter-wxclaw` 的调用。"""

    def get_adapter(self) -> WxClawAdapter:
        """获取当前 NoneBot 进程中的 WxClaw Adapter。

        Returns:
            WxClawAdapter: 已注册的 wxclaw adapter。

        Raises:
            RuntimeError: 当前进程没有注册 wxclaw adapter。
        """

        try:
            adapter = get_adapter(WxClawAdapter)
        except Exception as e:
            raise RuntimeError("当前 NoneBot 进程未加载 WxClaw 适配器") from e
        if not isinstance(adapter, WxClawAdapter):
            raise RuntimeError("当前 NoneBot 进程中的 WxClaw 适配器类型异常")
        return adapter

    def create_qr_login_session(self):
        """创建 wxclaw 扫码登录会话。

        Returns:
            QrLoginSession: wxclaw adapter 提供的登录会话对象。
        """

        return self.get_adapter().qr_login(auto_connect=True)

    async def connect_account(self, account: PlatformBotAccount) -> None:
        """根据数据库账号恢复 wxclaw 机器人连接。

        Args:
            account: 已保存的 wxclaw 机器人账号。
        """

        adapter = self.get_adapter()
        if account.account_id in adapter.bots:
            return

        token = decrypt_text(account.encrypted_token)
        result = WxClawLoginResult(
            connected=True,
            account_id=account.account_id,
            token=token,
            base_url=account.base_url or FIXED_BASE_URL,
            user_id=account.wx_user_id or "",
            message="restore from database",
        )
        adapter.connect_login_result(result, result.base_url or FIXED_BASE_URL)

    def is_connected(self, account_id: str) -> bool:
        """判断指定 wxclaw 机器人账号是否已经在线。"""

        try:
            return account_id in self.get_adapter().bots
        except RuntimeError:
            return False

    def select_bot_for_user(self, user_id: str) -> WxClawBot | None:
        """选择一个可向指定微信用户发送消息的 wxclaw bot。

        wxclaw 会在收到用户消息后保存 `context_token`。如果存在保存过
        该用户上下文的 bot，优先使用它；否则退化为第一个在线 wxclaw
        bot，让 adapter 自己按平台能力尝试发送。
        """

        bots = [bot for bot in self.get_adapter().bots.values() if isinstance(bot, WxClawBot)]
        for bot in bots:
            if bot.get_context_token(user_id):
                return bot
        return bots[0] if bots else None

    @staticmethod
    def account_info(account: PlatformBotAccount) -> WxClawAccountInfo:
        """把数据库账号转换成 wxclaw 配置对象。"""

        return WxClawAccountInfo(
            account_id=account.account_id,
            token=decrypt_text(account.encrypted_token),
            base_url=account.base_url or FIXED_BASE_URL,
            enabled=account.enabled,
        )
