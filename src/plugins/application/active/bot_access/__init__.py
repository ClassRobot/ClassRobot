from asyncio import create_task

from src.models import User
from src.shared import Emoji
from nonebot import logger, get_driver
from src.platform.bots import bot_account_service
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher
from src.platform.session.depends import UserOrCreatedDepends

from .commands import bot_access_cmd

SUPPORTED_PLATFORMS = {"微信", "wxclaw", "wechat", "weixin"}


@bot_access_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends, platform: str):
    """处理用户扫码接入第三方机器人账号。"""

    platform = platform.strip().lower()
    if platform not in SUPPORTED_PLATFORMS:
        await matcher.finish(Emoji.error + "暂时只支持接入微信机器人，请使用：接入机器人 微信")

    await access_wxclaw_bot(matcher, user)


async def access_wxclaw_bot(matcher: AlconnaMatcher, user: User) -> None:
    """执行 wxclaw 扫码登录与账号持久化流程。

    Args:
        matcher: 当前命令 matcher。
        user: 发起接入的系统用户。
    """

    try:
        provider = bot_account_service.wxclaw_provider
        if provider is None:
            raise RuntimeError("wxclaw provider 未初始化")
        login_session = provider.create_qr_login_session()
    except Exception as e:
        logger.exception(f"创建 wxclaw 扫码会话失败: {e}")
        await matcher.finish(Emoji.error + "当前未加载微信机器人适配器，无法生成接入二维码。")
        return

    async with login_session as session:
        qr_message = UniMessage.text("请使用微信扫描下方二维码完成机器人接入。\n")
        if session.qrcode_url:
            qr_message += UniMessage.image(url=session.qrcode_url)
            qr_message += UniMessage.text(f"\n如果图片无法显示，请打开：{session.qrcode_url}")
        await matcher.send(qr_message)

        result = await session.wait()

    if not result.connected:
        if result.need_verify_code:
            await matcher.finish(Emoji.error + "微信要求输入配对数字，本轮暂未开放该交互，请稍后重新发起接入。")
        await matcher.finish(Emoji.error + f"微信机器人接入失败：{result.message or '扫码超时或未确认'}")

    account = await bot_account_service.save_wxclaw_login_result(user, result)
    await matcher.finish(Emoji.success + f"微信机器人接入成功，账号实例：{account.account_id}\n" + "后续系统启动时会自动恢复该机器人连接。")


driver = get_driver()


@driver.on_startup
async def restore_user_bot_accounts() -> None:
    """启动时恢复数据库中启用的用户机器人账号。"""

    async def _restore() -> None:
        restored = await bot_account_service.restore_enabled_accounts()
        if restored:
            logger.success(f"已恢复 {len(restored)} 个用户接入机器人账号。")

    create_task(_restore())
