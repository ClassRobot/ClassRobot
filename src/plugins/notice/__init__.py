from asyncio import wait, sleep, create_task

from utils import Emoji
from nonebot import get_driver
from nonebot.params import Arg
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from utils.models import ScheduledNotice
from utils.models.annotated import UserOrCreatedDepends
from nonebot_plugin_alconna.uniseg.adapters import alter_get_exporter
from nonebot_plugin_alconna import Target, UniMsg, UniMessage, SupportAdapter, get_bot

from .schema import Notice
from .util import notice_work
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
    user: UserOrCreatedDepends,
    matcher: Matcher,
    notice_session: NoticeSessionDepends,
    notice_message: UniMessage = Arg(),
):
    if isinstance(notice_message, Message):
        notice_message = await UniMessage.generate(message=notice_message)
    if notices := await notice_session.call(notice_message):
        print(notices)
        if notices.reply:
            await matcher.send(
                (Emoji.error + notices.reply) if notices.is_invalid else notices.reply
            )
        if notices.is_invalid:
            await matcher.finish()
        await notices.create_all(user)
        for notice in notices:
            if notice.is_immediate:
                await notice_work(notice, user)
            else:
                notice.add_job(notice_work)
    else:
        await matcher.finish(Emoji.error + "处理失败")


driver = get_driver()


@driver.on_startup
async def _():
    sns = (await ScheduledNotice.select).all()
    tasks = []
    for sn in sns:
        notice = Notice.loads(sn)
        if notice.is_immediate:
            tasks.append(notice_work(notice))
        else:
            notice.add_job(notice_work)
    if tasks:

        async def _():
            await sleep(20)  # 等待一会让bot加载进来
            await wait(tasks)

        create_task(_())
