from utils import Emoji
from nonebot.rule import to_me
from utils.config import priority
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.message import handle_event
from nonebot import on_command, on_message
from nonebot_plugin_alconna import UniMsg, MsgTarget, UniMessage, SupportScope

from .util import ChatSessionDepends
from .schemas import AutoTask, AutoTaskList

auto_gpt = on_message(priority=1000, block=True, rule=to_me())
clear_message = on_command("清除聊天", priority=priority, block=True)


def update_message(task: AutoTask):
    def _get_message():
        message = UniMessage.text(task.command)
        for param in task.params:
            message += " "
            if param.type == "text":
                message += UniMessage.text(param.value)
            elif param.type == "image":
                message += UniMessage.image(param.value)
        return message

    return _get_message


@auto_gpt.handle()
async def _(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    message: UniMsg,
    target: MsgTarget,
    chat_session: ChatSessionDepends,
):
    if target.scope == SupportScope.wechat:
        await matcher.finish()
    elif chat_session.lock:
        await matcher.finish(Emoji.error + "我知道你很急，但是你先别急，等我处理完你的上一条消息。")
    auto_task = await chat_session.send_message(message)
    if isinstance(auto_task, AutoTaskList):
        if auto_task.is_violation:
            await matcher.finish(auto_task.reply)

        if auto_task.reply:
            await matcher.send(auto_task.reply)
            print(chat_session.messages.char_length())
        if not auto_task.need_confirm:
            for auto_task in auto_task.tasks:
                event.get_message = update_message(auto_task)  # type: ignore
                await handle_event(bot, event)
