from nonebot import on_command, on_message
from nonebot_plugin_alconna import UniMessage
from nonebot.rule import to_me
from nonebot.adapters import Bot, Event
from nonebot.params import EventMessage, CommandArg
from nonebot.message import handle_event
from nonebot.matcher import Matcher

from utils.AutoGPT import client_create
from utils.models.annotated import UserOrCreatedDepends
from .schemas import AutoTaskList, AutoTask
from .util import chat_session_manager

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
    chat = chat_session_manager.get_chat_session(user.id)
    auto_task = await chat.send_message(message.extract_plain_text())
    if isinstance(auto_task, AutoTaskList):
        if auto_task.reply:
            await matcher.send(auto_task.reply)
        if not auto_task.need_confirm:
            for auto_task in auto_task.tasks:
                event.get_message = update_message(auto_task)  # type: ignore
                await handle_event(bot, event)
    #     if auto_task.reply:
    #         await matcher.send(auto_task.reply)
    # print(auto_task)
    # # await matcher.finish(text)
    # # def _get_message():
    # #     return message.__class__("清除聊天")
    #     if auto_task.need_confirm
    # event.get_message = _get_message  # type: ignore
    # await handle_event(bot, event)


# @break_message.handle()
# async def _(matcher: Matcher, message: UniMessage = CommandArg()):
#     # print("Break", event.get_message())
#     await matcher.finish(message)  # type: ignore
