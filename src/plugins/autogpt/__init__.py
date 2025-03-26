import re
from typing import Callable

from utils import Emoji
from nonebot.rule import to_me
from utils.helper import Helper
from utils.roles import UserRole
from utils.config import priority
from nonebot.matcher import Matcher
from nonebot.message import handle_event
from nonebot_plugin_htmlrender import md_to_pic
from nonebot.adapters import Bot, Event, Message
from nonebot import logger, on_command, on_message
from nonebot.adapters.qq.exception import ActionFailed
from nonebot_plugin_alconna import Target, UniMsg, MsgTarget, UniMessage, SupportScope

from .util import ChatSessionDepends
from .schema import AutoTask, AutoTaskList

auto_gpt = on_message(priority=priority * 10, block=True, rule=to_me())
clear_chat = on_command("清空聊天", aliases={"重置聊天", "聊天清空", "聊天重置"}, priority=priority, block=True)


def update_message(task: AutoTask, target: Target) -> Callable[[], Message]:
    message = UniMessage.text(task.command)
    for param in task.params:
        if param.type == "text":
            message += UniMessage.text(" " + param.value)
        elif param.type == "image":
            message += UniMessage.image(url=param.value)
    msg = message.export_sync(adapter=target.adapter)
    return lambda: msg


@clear_chat.handle()
async def _(
    matcher: Matcher,
    chat_session: ChatSessionDepends,
):
    chat_session.clear()
    await matcher.finish("已清空聊天记录")


@auto_gpt.handle()
async def _(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    message: UniMsg,
    target: MsgTarget,
    chat_session: ChatSessionDepends,
):
    print(target.adapter, target.scope, target.platform)
    if target.scope == SupportScope.wechat:
        await matcher.finish()
    elif chat_session.lock:
        await matcher.finish(Emoji.error + "我知道你很急，但是你先别急，等我处理完你的上一条消息。")
    try:
        auto_task = await chat_session.send_message(message)
    except Exception as e:
        logger.exception(e)
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
    if not isinstance(auto_task, AutoTaskList):
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
    elif auto_task.is_violation:
        await matcher.finish(auto_task.reply)

    if auto_task.reply:
        try:
            # reply行数大于10时转成图片发送
            if auto_task.reply.count("\n") < 10:
                # 正则表达式查找Markdown图片格式
                pattern = r"!\[image\]\(([^)]+)\)"
                parts = []
                last_idx = 0
                matches = list(re.finditer(pattern, auto_task.reply))

                # 处理找到的每个匹配项
                for match in matches:
                    # 添加匹配前的文本
                    if match.start() > last_idx:
                        parts.append(auto_task.reply[last_idx : match.start()])
                    # 添加图片URL
                    parts.append(match.group(1))
                    last_idx = match.end()

                # 添加最后一个匹配后的剩余文本
                if last_idx < len(auto_task.reply):
                    parts.append(auto_task.reply[last_idx:])

                # 如果没有找到任何匹配项，直接使用原始文本
                if not matches:
                    parts = [auto_task.reply]

                # 过滤空字符串
                parts = [part for part in parts if part]

                reply_message = UniMessage()
                for part in parts:
                    if part.startswith("http://") or part.startswith("https://"):
                        reply_message += UniMessage.image(url=part).export_sync(adapter=target.adapter)
                    else:
                        reply_message += part.replace(".", "⋅")
                await matcher.send(await reply_message.export(adapter=target.adapter))
            else:
                pic = UniMessage.image(raw=await md_to_pic(auto_task.reply)) + "内容过长转为图片发送！"
                await matcher.send(await pic.export(adapter=target.adapter))
        except ActionFailed as e:
            logger.exception(e)
            await matcher.finish(Emoji.error + (e.message or str(e.status_code)))
    if not auto_task.need_confirm:
        for auto_task in auto_task.tasks:
            if chat_session.helpers.get_helper(auto_task.command):
                event = event.copy()
                event.__uniseg_message_id__ = str(id(event))
                event.get_message = update_message(auto_task, target)
                await handle_event(bot, event)
            else:
                await matcher.send(Emoji.error + f"无法调用`{auto_task.command}`命令")


__helpers__ = [
    Helper(
        command="清空聊天",
        description="清空机器人于用户的聊天内容",
        roles={UserRole.user},
        ai_description="当用户对于机器人的回复非常不满意，或者存在违规内容时候机器人可以主动清空聊天记录",
    )
]
