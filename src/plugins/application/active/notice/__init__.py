from asyncio import wait, sleep, create_task

from src.shared import Emoji
from nonebot import get_driver
from nonebot.params import Arg
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from src.models import ScheduledNotice
from src.platform.session.depends import UserOrCreatedDepends
from nonebot_plugin_alconna import UniMsg, UniMessage, AlconnaMatcher

from .schema import Notice
from .util import notice_work
from .commands import notice_cmd, query_notice_cmd, delete_notice_cmd
from .depends import QueryNoticeDepends, DeleteNoticeDepends, NoticeSessionDepends

# --------------------------------- 创建通知 ---------------------------------


# @notice_cmd.handle()
# async def _(matcher: Matcher, message: UniMsg):
#     if message and len(message.extract_plain_text()) > 2:
#         matcher.state["notice_message"] = message


# @notice_cmd.got(
#     "notice_message",
#     prompt="需要发什么样的通知发给谁呢？您可以用白话文描述您的通知的内容，要清晰的描述通知人、通知事项、通知时间等信息",
# )
# async def _(
#     user: UserOrCreatedDepends,
#     matcher: Matcher,
#     notice_session: NoticeSessionDepends,
#     notice_message: UniMessage = Arg(),
# ):
#     if isinstance(notice_message, Message):
#         notice_message = await UniMessage.generate(message=notice_message)
#     if notices := await notice_session.call(notice_message):
#         print(notices)
#         if notices.reply:
#             await matcher.send((Emoji.error + notices.reply) if notices.is_invalid else notices.reply)
#         if notices.is_invalid:
#             await matcher.finish()
#         await notices.create_all(user)
#         for notice in notices:
#             if notice.is_immediate:
#                 await notice_work(notice, user)
#             else:
#                 notice.add_job(notice_work)
#     else:
#         await matcher.finish(Emoji.error + "处理失败")


# # --------------------------------- 查询自己创建的所有通知 ---------------------------------


# @query_notice_cmd.handle()
# async def _(matcher: AlconnaMatcher, query_notice: QueryNoticeDepends):
#     notice_list = await query_notice.get_notices()
#     if notice_list:
#         await matcher.finish(query_notice.render_string(notice_list))

#     await matcher.finish(Emoji.error + "您似乎还未创建通知")


# # --------------------------------- 删除自己创建的通知 ---------------------------------


# @delete_notice_cmd.handle()
# async def _(matcher: AlconnaMatcher, delete_notice: DeleteNoticeDepends, notice_id: list[str]):
#     if not (notice_ids := [int(nid) for nid in notice_id if nid.isdigit()]):
#         await matcher.finish(Emoji.error + "您需要输入通知ID(NID)才能删除")

#     for nid in notice_ids:
#         if notice := await delete_notice.get_notice(nid):
#             await delete_notice.delete_notice(notice)

#     await matcher.finish(Emoji.success + "删除完成！")


# driver = get_driver()


# @driver.on_startup
# async def startup_create_notice():
#     """在启动时创建所有通知,如果是已经结束的通知则紧急发送掉"""
#     sns = (await ScheduledNotice.select).all()
#     tasks = []
#     for sn in sns:
#         notice = Notice.loads(sn)
#         if notice.is_immediate:
#             tasks.append(notice_work(notice))
#         else:
#             notice.add_job(notice_work)
#     if tasks:

#         async def _():
#             await sleep(20)  # 等待一会让bot加载进来
#             await wait(tasks)

#         create_task(_())
