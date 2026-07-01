from time import perf_counter

from src.shared import Emoji
from nonebot.rule import to_me
from nonebot.matcher import Matcher
from nonebot import logger, on_message
from nonebot.adapters import Bot, Event
from src.platform.config import priority
from nonebot_plugin_alconna import UniMsg
from src.platform.session import EventSession
from nonebot.adapters.qq.exception import ActionFailed
from src.core.agent.runtime.schema import AutoTaskList
from src.core.agent.runtime.formatting import preview_text
from nonebot.adapters.onebot.v12.exception import NetworkError
from src.core.agent.runtime import RuntimeContext, ChatSessionDepends
from src.core.agent.runtime.workflow import collect_observation_display_summaries
from src.core.agent.runtime.execution import dispatch_auto_task, dispatch_auto_tasks

from . import commands
from .commands import clear_chat
from .messaging import send_progress, send_markdown_reply, send_long_markdown_reply

auto_gpt = on_message(priority=priority * 10, block=True, rule=to_me())


@clear_chat.handle()
async def _(
    matcher: Matcher,
    chat_session: ChatSessionDepends,
):
    """处理当前命令或事件逻辑。"""
    await chat_session.clear()
    await matcher.finish("已清空聊天记录")


def _build_runtime_context(chat_session, platform: EventSession, event: Event) -> RuntimeContext:
    """根据当前会话与平台事件构造一轮运行时上下文。"""

    return RuntimeContext(
        user_id=chat_session.user_id,
        platform=platform.platform,
        platform_name=platform.platform_name,
        channel_id=platform.channel_id,
        guild_id=platform.guild_id,
        message_id=str(getattr(event, "message_id", "") or ""),
    )


async def _send_initial_reply(matcher: Matcher, bot: Bot, chat_session, text: str) -> None:
    """发送本轮 Host 认可的首条用户可见回复，并统一异常降级。"""

    reply_started = perf_counter()
    logger.info(
        f'AutoGPT trace "{chat_session.last_trace_id}" sending initial reply '
        f'len={len(text)} preview="{preview_text(text)}"'
    )
    try:
        # reply 行数大于 10 时转成图片发送；保持模块级函数名调用以便测试可替换。
        if text.count("\n") < 10:
            await send_markdown_reply(matcher, bot, text)
        else:
            await send_long_markdown_reply(matcher, bot, text)
    except ActionFailed as e:
        logger.exception(e)
        await matcher.finish(Emoji.error + (e.message or str(e.status_code)))
    except NetworkError as e:
        logger.exception(e)
        await matcher.finish(Emoji.error + "内部异常, 请重试！")
    logger.info(
        f'AutoGPT trace "{chat_session.last_trace_id}" sent initial reply ' f"in {perf_counter() - reply_started:.3f}s"
    )


async def _run_workflow(matcher: Matcher, bot: Bot, chat_session, platform: EventSession, workflow) -> None:
    """执行已生成步骤的任务流，并把最终回复发回用户。"""

    workflow_started = perf_counter()
    logger.info(
        f'AutoGPT trace "{chat_session.last_trace_id}" starting workflow execution '
        f"kind={workflow.kind} status={workflow.status} steps={len(workflow.steps)}"
    )
    execution = await chat_session.execute_task_workflow(
        workflow,
        dispatcher=lambda task: dispatch_auto_task(
            task,
            trace_id=chat_session.last_trace_id,
            user_id=chat_session.user_id,
            roles=chat_session.helpers.active_roles,
            platform_id=platform.platform,
            channel_id=platform.channel_id,
            guild_id=platform.guild_id,
            platform_name=platform.platform_name,
        ),
        trace_id=chat_session.last_trace_id,
        progress_reporter=lambda text: send_progress(matcher, text),
    )
    logger.info(
        f'AutoGPT trace "{chat_session.last_trace_id}" workflow execution finished '
        f"in {perf_counter() - workflow_started:.3f}s status={execution.workflow.status} "
        f'observations={len(execution.observations)} final_reply_len={len(execution.final_reply or "")} '
        f'user_message_len={len(execution.user_message or "")}'
    )
    if not execution.final_reply:
        return
    user_message = (
        Emoji.error + execution.final_reply if execution.workflow.status == "failed" else execution.final_reply
    )
    send_started = perf_counter()
    logger.info(
        f'AutoGPT trace "{chat_session.last_trace_id}" sending execution final reply '
        f'len={len(user_message)} preview="{preview_text(user_message)}"'
    )
    await send_markdown_reply(matcher, bot, user_message)
    logger.info(
        f'AutoGPT trace "{chat_session.last_trace_id}" sent execution final reply '
        f"in {perf_counter() - send_started:.3f}s"
    )


async def _run_direct_tasks(matcher: Matcher, bot: Bot, chat_session, platform: EventSession, auto_task) -> None:
    """无任务流时，直接调度本轮自动任务并回写观察、汇总结果。"""

    observations = await dispatch_auto_tasks(
        auto_task.tasks,
        helpers=chat_session.helpers,
        trace_id=chat_session.last_trace_id,
        user_id=chat_session.user_id,
        roles=chat_session.helpers.active_roles,
        platform_id=platform.platform,
        channel_id=platform.channel_id,
        guild_id=platform.guild_id,
        platform_name=platform.platform_name,
    )
    if not observations:
        return
    chat_session.record_observations(observations, trace_id=chat_session.last_trace_id)
    executed_count = sum(1 for observation in observations if observation.dispatch_type == "command")
    if executed_count:
        await send_markdown_reply(matcher, bot, f"已运行 {executed_count} 条命令。")
    display_summaries = collect_observation_display_summaries(observations)
    if display_summaries:
        await send_markdown_reply(matcher, bot, "\n\n".join(display_summaries))


@auto_gpt.handle()
async def _(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    message: UniMsg,
    platform: EventSession,
    chat_session: ChatSessionDepends,
):
    """AutoGPT 主入口：解析消息、发送首条回复，并按任务流/直接任务收尾。"""
    if chat_session.lock:
        await matcher.finish(Emoji.error + "上一条消息还在处理中，我处理完后再接着看这条。")
    try:
        turn_result = await chat_session.send_message(
            message,
            progress_reporter=lambda text: send_progress(matcher, text),
            runtime_context=_build_runtime_context(chat_session, platform, event),
        )
    except Exception as e:
        logger.exception(f'AutoGPT trace "{chat_session.last_trace_id}" failed: {e}')
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
        return

    auto_task = turn_result.auto_tasks if turn_result else None
    logger.info(
        f'AutoGPT trace "{chat_session.last_trace_id}" plugin received turn result '
        f"workflow={turn_result.workflow.kind if turn_result and turn_result.workflow else None} "
        f'reply_len={len(auto_task.reply or "") if auto_task else 0} '
        f"tasks={len(auto_task.tasks) if auto_task else 0} "
        f"need_confirm={auto_task.need_confirm if auto_task else None}"
    )
    if turn_result and turn_result.workflow and auto_task and auto_task.need_confirm:
        await chat_session.record_workflow(turn_result.workflow, trace_id=chat_session.last_trace_id)

    if not isinstance(auto_task, AutoTaskList):
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
        return
    if auto_task.is_violation:
        await matcher.finish(chat_session.user_visible_initial_reply(turn_result) or auto_task.reply)

    initial_reply = chat_session.user_visible_initial_reply(turn_result)
    if initial_reply:
        await _send_initial_reply(matcher, bot, chat_session, initial_reply)

    if auto_task.need_confirm:
        return

    workflow = turn_result.workflow if turn_result else None
    if workflow and workflow.steps:
        await _run_workflow(matcher, bot, chat_session, platform, workflow)
    elif workflow:
        logger.info(
            f'AutoGPT trace "{chat_session.last_trace_id}" skipped workflow execution because no steps were generated '
            f"kind={workflow.kind} status={workflow.status}"
        )
    else:
        await _run_direct_tasks(matcher, bot, chat_session, platform, auto_task)
