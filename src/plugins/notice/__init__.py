from utils import Emoji
from nonebot.params import Arg
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from nonebot_plugin_alconna import UniMsg, UniMessage

from .commands import notice_cmd
from .depends import NoticeSessionDepends


@notice_cmd.handle()
async def _(matcher: Matcher, message: UniMsg):
    if message and len(message.extract_plain_text()) > 2:
        matcher.state["notice_message"] = message


@notice_cmd.got(
    "notice_message",
    prompt="需要发什么样的通知发给谁呢？您可以用白话文描述您的通知的内容，要清晰的描述通知人、通知事项、通知时间等信息",
)
async def _(
    matcher: Matcher,
    notice_session: NoticeSessionDepends,
    notice_message: UniMessage = Arg(),
):
    if isinstance(notice_message, Message):
        notice_message = await UniMessage.generate(message=notice_message)
    if notice := await notice_session.call(notice_message):
        if notice.reply:
            await matcher.finish(notice.reply)
    else:
        await matcher.finish(Emoji.error + "处理失败")
