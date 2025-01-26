from nonebot.rule import to_me
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.message import handle_event
from nonebot import on_command, on_message
from nonebot_plugin_alconna import UniMessage
from nonebot.params import CommandArg, EventMessage
from utils.models.annotated import UserOrCreatedDepends
from nonebot.adapters.ntchat import MessageEvent as NTChatMessageEvent

from .util import chat_session_manager
from .schemas import AutoTask, AutoTaskList

auto_gpt = on_message(priority=1000, block=True, rule=to_me())
clear_message = on_command("清除聊天", priority=100, block=True)


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
    user: UserOrCreatedDepends,
    message: UniMessage = EventMessage(),
):
    if isinstance(event, NTChatMessageEvent):
        await matcher.finish()
    chat = chat_session_manager.get_chat_session(user.id)
    auto_task = await chat.send_message(message.extract_plain_text())
    if isinstance(auto_task, AutoTaskList):
        if auto_task.is_violation:
            await matcher.finish("您发送的内容包含违规信息，已经被屏蔽")
        if auto_task.reply:
            await matcher.send(auto_task.reply)
            print(chat.messages.char_length())
        if not auto_task.need_confirm:
            for auto_task in auto_task.tasks:
                event.get_message = update_message(auto_task)  # type: ignore
                await handle_event(bot, event)
