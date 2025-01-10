from nonebot import on_command, on_message
from nonebot_plugin_alconna import UniMessage
from nonebot.rule import to_me
from nonebot.adapters import Bot, Event
from nonebot.params import EventMessage, CommandArg
from nonebot.message import handle_event
from nonebot.matcher import Matcher

auto_gpt = on_message(priority=1000, block=True, rule=to_me())
break_message = on_command("break", priority=100, block=True)


@auto_gpt.handle()
async def _(bot: Bot, event: Event, message: UniMessage = EventMessage()):
    print("AutoGPT", message)

    def _get_message():
        return message.__class__("break") + message

    event.get_message = _get_message  # type: ignore
    await handle_event(bot, event)


@break_message.handle()
async def _(matcher: Matcher, message: UniMessage = CommandArg()):
    # print("Break", event.get_message())
    await matcher.finish(message)  # type: ignore
