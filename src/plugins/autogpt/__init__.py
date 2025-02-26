from utils import Emoji
from nonebot.rule import to_me
from utils.helper import Helper
from utils.roles import UserRole
from utils.config import priority
from nonebot.matcher import Matcher
from nonebot.adapters import Bot, Event
from nonebot.message import handle_event
from nonebot import logger, on_command, on_message
from nonebot.adapters.qq.exception import ActionFailed
from nonebot_plugin_alconna import Target, UniMsg, MsgTarget, UniMessage, SupportScope

from .util import ChatSessionDepends
from .schemas import AutoTask, AutoTaskList

auto_gpt = on_message(priority=priority * 10, block=True, rule=to_me())
clear_chat = on_command("清空聊天", priority=priority, block=True)


def update_message(task: AutoTask, target: Target):
    def _get_message():
        message = UniMessage.text(task.command)
        for param in task.params:
            if param.type == "text":
                message += UniMessage.text(" " + param.value)
            elif param.type == "image":
                message += UniMessage.image(param.value)
        return message.export_sync(adapter=target.adapter)

    return _get_message


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
    if target.scope == SupportScope.wechat:
        await matcher.finish()
    elif chat_session.lock:
        await matcher.finish(Emoji.error + "我知道你很急，但是你先别急，等我处理完你的上一条消息。")
    try:
        auto_task = await chat_session.send_message(message)
    except Exception as e:
        logger.exception(e)
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
    if isinstance(auto_task, AutoTaskList):
        if auto_task.is_violation:
            await matcher.finish(auto_task.reply)

        if auto_task.reply:
            try:
                await matcher.send(auto_task.reply.replace(".", "⋅"))
            except ActionFailed as e:
                logger.exception(e)
                await matcher.finish(Emoji.error + (e.message or str(e.status_code)))
        if not auto_task.need_confirm:
            for auto_task in auto_task.tasks:
                if chat_session.helpers.get_helper(auto_task.command):
                    event.get_message = update_message(auto_task, target)  # type: ignore
                    await handle_event(bot, event)
                else:
                    await matcher.send(Emoji.error + f"无法调用`{auto_task.command}`命令")


__helpers__ = [
    Helper(
        command="清空聊天",
        description="清空机器人于用户的聊天内容",
        roles={UserRole.user},
    )
]
