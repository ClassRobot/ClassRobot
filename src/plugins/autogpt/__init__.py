from typing import Callable

from utils import Emoji
from nonebot.rule import to_me
from utils.helper import Helper, HelperScope
from utils.roles import UserRole
from utils.config import priority
from utils.skills import markdown_to_image_skill
from nonebot.matcher import Matcher
from nonebot.message import handle_event
from nonebot.adapters import Bot, Event, Message
from nonebot import logger, on_command, on_message
from nonebot.adapters.qq.exception import ActionFailed
from nonebot.adapters.onebot.v12.exception import NetworkError
from nonebot_plugin_alconna import Target, UniMsg, MsgTarget, UniMessage

from .schema import Param, AutoTask, AutoTaskList, CommandObservation
from .util import ChatSessionDepends, markdown_to_message
from .workflow import WorkflowExecutor

auto_gpt = on_message(priority=priority * 10, block=True, rule=to_me())
clear_chat = on_command("清空聊天", aliases={"重置聊天", "聊天清空", "聊天重置"}, priority=priority, block=True)


def build_message(command: str, params: list[Param], target: Target) -> Message:
    """将 AI 规划出的项目命令转换为当前适配器消息。"""

    message = UniMessage.text(command)
    for param in params:
        if param.type == "text":
            message += UniMessage.text(" " + param.value)
        elif param.type == "image":
            message += UniMessage.image(url=param.value)
    return message.export_sync(adapter=target.adapter)


def update_message(task: AutoTask, target: Target) -> Callable[[], Message]:
    """更新消息。"""

    return lambda: build_message(task.command, [param for param in task.params if not param.separate], target)


def update_separate_message(param: Param, target: Target) -> Callable[[], Message]:
    """生成需要单独投递的命令参数消息。"""

    if param.type == "image":
        message = UniMessage.image(url=param.value).export_sync(adapter=target.adapter)
    else:
        message = UniMessage.text(param.value).export_sync(adapter=target.adapter)
    return lambda: message


async def dispatch_auto_task(
    bot: Bot,
    event: Event,
    task: AutoTask,
    target: Target,
    trace_id: str = "",
) -> list[CommandObservation]:
    """把自动任务重新投递给 NoneBot，复用原有 matcher 与依赖。"""

    observations: list[CommandObservation] = []
    command_params = [param for param in task.params if not param.separate]
    logger.info(f'AutoGPT trace "{trace_id}" dispatch command "{task.command}"')
    next_event = event.copy()
    next_event.__uniseg_message_id__ = str(id(next_event))
    next_event.get_message = update_message(task, target)
    try:
        await handle_event(bot, next_event)
        observations.append(
            CommandObservation(
                trace_id=trace_id,
                command=task.command,
                params=command_params,
                dispatch_type="command",
                success=True,
                message="命令已投递给 NoneBot 事件系统。",
            )
        )
    except Exception as error:
        logger.exception(error)
        observations.append(
            CommandObservation(
                trace_id=trace_id,
                command=task.command,
                params=command_params,
                dispatch_type="command",
                success=False,
                message=f"命令投递失败：{error}",
            )
        )
        return observations

    for param in task.params:
        if param.separate:
            next_event = event.copy()
            next_event.__uniseg_message_id__ = str(id(next_event))
            next_event.get_message = update_separate_message(param, target)
            try:
                await handle_event(bot, next_event)
                observations.append(
                    CommandObservation(
                        trace_id=trace_id,
                        command=task.command,
                        params=[param],
                        dispatch_type="separate_param",
                        success=True,
                        message="分离参数已投递给 NoneBot 事件系统。",
                    )
                )
            except Exception as error:
                logger.exception(error)
                observations.append(
                    CommandObservation(
                        trace_id=trace_id,
                        command=task.command,
                        params=[param],
                        dispatch_type="separate_param",
                        success=False,
                        message=f"分离参数投递失败：{error}",
                    )
                )
                break
    return observations


async def send_progress(matcher: Matcher, text: str) -> None:
    """发送 AutoGPT 阶段性进度反馈。"""

    await matcher.send(text)


@clear_chat.handle()
async def _(
    matcher: Matcher,
    chat_session: ChatSessionDepends,
):
    """处理当前命令或事件逻辑。"""
    await chat_session.clear()
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
    """处理当前命令或事件逻辑。"""
    if chat_session.lock:
        await matcher.finish(Emoji.error + "我知道你很急，但是你先别急，等我处理完你的上一条消息。")
    try:
        turn_result = await chat_session.send_message(
            message,
            progress_reporter=lambda text: send_progress(matcher, text),
        )
    except Exception as e:
        logger.exception(f'AutoGPT trace "{chat_session.last_trace_id}" failed: {e}')
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
        return

    auto_task = turn_result.auto_tasks if turn_result else None
    if turn_result and turn_result.workflow and auto_task and auto_task.need_confirm:
        await chat_session.record_workflow(turn_result.workflow, trace_id=chat_session.last_trace_id)

    if not isinstance(auto_task, AutoTaskList):
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
        return
    elif auto_task.is_violation:
        await matcher.finish(auto_task.reply)
        return

    if auto_task.reply:
        try:
            # reply行数大于10时转成图片发送
            if auto_task.reply.count("\n") < 10:
                await matcher.send(await markdown_to_message(auto_task.reply).export(adapter=target.adapter, bot=bot))
            else:
                pic = UniMessage.image(raw=await markdown_to_image_skill.to_image(auto_task.reply)) + UniMessage.text(
                    "文字太长已转为图片发送"
                )
                await matcher.send(await pic.export(adapter=target.adapter, bot=bot))
        except ActionFailed as e:
            logger.exception(e)
            await matcher.finish(Emoji.error + (e.message or str(e.status_code)))
        except NetworkError as e:
            logger.exception(e)
            await matcher.finish(Emoji.error + "内部异常, 请重试！")
    if not auto_task.need_confirm:
        workflow = turn_result.workflow if turn_result else None
        if workflow:
            executor = WorkflowExecutor(
                dispatcher=lambda task: dispatch_auto_task(
                    bot, event, task, target, trace_id=chat_session.last_trace_id
                )
            )
            execution = await executor.execute(workflow)
            if execution.observations:
                chat_session.record_observations(execution.observations, trace_id=chat_session.last_trace_id)
            await chat_session.record_workflow(execution.workflow, trace_id=chat_session.last_trace_id)
            if execution.user_message:
                await matcher.send(Emoji.error + execution.user_message)
        else:
            observations: list[CommandObservation] = []
            for task in auto_task.tasks:
                if chat_session.helpers.get_helper(task.command):
                    observations.extend(
                        await dispatch_auto_task(bot, event, task, target, trace_id=chat_session.last_trace_id)
                    )
                else:
                    observations.append(
                        CommandObservation(
                            trace_id=chat_session.last_trace_id,
                            command=task.command,
                            params=task.params,
                            dispatch_type="missing_command",
                            success=False,
                            message="命令不存在，未投递。",
                        )
                    )
                    await matcher.send(Emoji.error + f"无法调用`{task.command}`命令，因为该命令不存在！")
            if observations:
                chat_session.record_observations(observations, trace_id=chat_session.last_trace_id)


__helpers__ = [
    Helper(
        command="清空聊天",
        description="清空机器人于用户的聊天内容",
        roles={UserRole.user},
        scopes={HelperScope.user},
        ai_description="当用户对于机器人的回复非常不满意，或者存在违规内容时候机器人可以主动清空聊天记录",
    )
]
