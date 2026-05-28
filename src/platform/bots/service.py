from __future__ import annotations

from typing import Literal
from datetime import datetime
from dataclasses import dataclass

from nonebot import logger
from src.core.auth.crypto import encrypt_text
from src.models import User, PlatformBotAccount

from .providers.wxclaw import WxClawBotProvider, WxClawLoginResultLike

BotAccountStatus = Literal["created", "connected", "failed", "disabled"]


@dataclass(slots=True)
class BotAccountService:
    """管理用户接入的第三方机器人账号。"""

    wxclaw_provider: WxClawBotProvider | None = None

    def __post_init__(self) -> None:
        """初始化默认 provider。"""

        if self.wxclaw_provider is None:
            self.wxclaw_provider = WxClawBotProvider()

    async def save_wxclaw_login_result(self, owner: User, result: WxClawLoginResultLike) -> PlatformBotAccount:
        """保存 wxclaw 扫码登录结果。

        Args:
            owner: 接入该机器人实例的系统用户。
            result: wxclaw adapter 返回的登录结果。

        Returns:
            PlatformBotAccount: 已创建或更新的机器人账号。

        Raises:
            ValueError: 登录结果缺少必要凭证。
        """

        if not result.connected or not result.account_id or not result.token:
            raise ValueError(result.message or "微信机器人登录结果缺少账号或 token")

        encrypted_token = encrypt_text(result.token)
        existing = await PlatformBotAccount.get_account("wxclaw", result.account_id)
        payload = {
            "owner_user_id": owner.id,
            "encrypted_token": encrypted_token,
            "base_url": result.base_url or "",
            "wx_user_id": result.user_id or None,
            "enabled": True,
            "status": "connected",
            "last_error": None,
            "last_connected_at": datetime.now(),
        }
        if existing is not None:
            updated = await existing.update(**payload)
            if updated is None:
                raise RuntimeError("微信机器人账号更新失败")
            return updated

        return await PlatformBotAccount(
            platform="wxclaw",
            account_id=result.account_id,
            **payload,
        ).create()

    async def restore_enabled_accounts(self) -> list[PlatformBotAccount]:
        """恢复所有启用状态的机器人账号。

        Returns:
            list[PlatformBotAccount]: 成功恢复或已在线的账号列表。
        """

        accounts = await PlatformBotAccount.filter(platform="wxclaw", enabled=True).all()
        restored: list[PlatformBotAccount] = []
        for account in accounts:
            try:
                await self.connect_account(account)
                refreshed = await account.mark_connected()
                restored.append(refreshed or account)
            except Exception as e:
                logger.exception(f"恢复 wxclaw 机器人账号 {account.account_id} 失败: {e}")
                await account.mark_failed(str(e))
        return restored

    async def connect_account(self, account: PlatformBotAccount) -> None:
        """连接一个已保存的机器人账号。

        Args:
            account: 已保存的机器人账号。
        """

        if account.platform != "wxclaw":
            raise ValueError(f"暂不支持连接平台: {account.platform}")
        if self.wxclaw_provider is None:
            raise RuntimeError("wxclaw provider 未初始化")
        await self.wxclaw_provider.connect_account(account)

    async def disable_account(self, account: PlatformBotAccount) -> PlatformBotAccount | None:
        """禁用机器人账号，后续启动不再自动恢复。"""

        return await account.update(enabled=False, status="disabled")

    async def get_account_status(self, account: PlatformBotAccount) -> str:
        """获取机器人账号当前运行状态。"""

        if account.platform != "wxclaw" or self.wxclaw_provider is None:
            return account.status
        if self.wxclaw_provider.is_connected(account.account_id):
            return "connected"
        return account.status


bot_account_service = BotAccountService()
