from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


class FakeWxClawLoginResult:
    """测试用 wxclaw 登录结果。"""

    connected = True
    account_id = "wx-bot-001"
    token = "raw-wx-token"
    base_url = "https://ilinkai.weixin.qq.com"
    user_id = "wx-user-001"
    message = "ok"
    need_verify_code = False


class FakeQrLoginSession:
    """测试用二维码登录会话。"""

    qrcode_url = "https://example.invalid/wx-qrcode.png"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def wait(self):
        return FakeWxClawLoginResult()


class FakeWxClawProvider:
    """测试用 wxclaw provider。"""

    def create_qr_login_session(self):
        return FakeQrLoginSession()


async def test_user_can_access_wxclaw_bot(app, onebot, send_recorder, monkeypatch):
    from src.models import PlatformBotAccount
    from src.core.auth.crypto import decrypt_text
    from src.platform.commands.registry import command_registry
    from src.plugins.application.active.bot_access import bot_account_service
    from src.plugins.application.active.bot_access.commands import bot_access_cmd

    monkeypatch.setattr(bot_account_service, "wxclaw_provider", FakeWxClawProvider())

    async with app.test_matcher(bot_access_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("接入机器人 微信", user_id=18001, nickname="微信用户")
        ctx.receive_event(bot, event)

    recorder.assert_any("扫描")
    recorder.assert_any("接入成功", "wx-bot-001")

    account = await PlatformBotAccount.get_account("wxclaw", "wx-bot-001")
    assert account is not None
    assert account.owner.nickname == "微信用户"
    assert account.encrypted_token != "raw-wx-token"
    assert decrypt_text(account.encrypted_token) == "raw-wx-token"
    assert account.status == "connected"
    spec = command_registry.get("接入机器人")
    assert spec is not None
    assert not spec.agent_callable


async def test_wxclaw_access_reports_adapter_unavailable(app, onebot, send_recorder, monkeypatch):
    from src.plugins.application.active.bot_access import bot_account_service
    from src.plugins.application.active.bot_access.commands import bot_access_cmd

    class UnavailableProvider:
        def create_qr_login_session(self):
            raise RuntimeError("adapter missing")

    monkeypatch.setattr(bot_account_service, "wxclaw_provider", UnavailableProvider())

    async with app.test_matcher(bot_access_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("接入机器人 微信", user_id=18002, nickname="微信用户")
        ctx.receive_event(bot, event)

    recorder.assert_any("未加载微信机器人适配器")


async def test_wxclaw_notification_uses_native_text_sender(monkeypatch, models):
    from src.models import User, UserBind
    from nonebot_plugin_alconna import UniMessage
    from src.platform.messaging import push_user_message

    user = await User.create_user(nickname="通知用户", username="wx_notice_user")
    await UserBind.bind_user("wxclaw.private", "wx-user-002", user)
    user = await User.filter(id=user.id).first()

    sent: list[tuple[str, str]] = []

    class FakeWxClawBot:
        async def send_text(self, account_id: str, text: str):
            sent.append((account_id, text))

    class FakeProvider:
        def select_bot_for_user(self, user_id: str):
            assert user_id == "wx-user-002"
            return FakeWxClawBot()

    monkeypatch.setattr("src.platform.messaging.WxClawBotProvider", FakeProvider)

    await push_user_message(user, UniMessage.text("微信通知"))

    assert sent == [("wx-user-002", "微信通知")]


async def test_restore_enabled_bot_accounts_marks_failed_without_blocking():
    from src.core.auth.crypto import encrypt_text
    from src.models import User, PlatformBotAccount
    from src.platform.bots import BotAccountService

    owner = await User.create_user(nickname="恢复用户", username="restore_user")
    ok_account = await PlatformBotAccount(
        owner_user_id=owner.id,
        platform="wxclaw",
        account_id="wx-ok",
        encrypted_token=encrypt_text("ok-token"),
        base_url="https://ilinkai.weixin.qq.com",
        enabled=True,
        status="created",
    ).create()
    failed_account = await PlatformBotAccount(
        owner_user_id=owner.id,
        platform="wxclaw",
        account_id="wx-failed",
        encrypted_token=encrypt_text("failed-token"),
        base_url="https://ilinkai.weixin.qq.com",
        enabled=True,
        status="created",
    ).create()

    class FakeProvider:
        async def connect_account(self, account):
            if account.account_id == "wx-failed":
                raise RuntimeError("token expired")

        def is_connected(self, account_id: str):
            return account_id == "wx-ok"

    service = BotAccountService(wxclaw_provider=FakeProvider())

    restored = await service.restore_enabled_accounts()

    assert [account.account_id for account in restored] == ["wx-ok"]
    ok_account = await PlatformBotAccount.filter(id=ok_account.id).first()
    failed_account = await PlatformBotAccount.filter(id=failed_account.id).first()
    assert ok_account is not None and ok_account.status == "connected"
    assert failed_account is not None
    assert failed_account.status == "failed"
    assert "token expired" in (failed_account.last_error or "")
