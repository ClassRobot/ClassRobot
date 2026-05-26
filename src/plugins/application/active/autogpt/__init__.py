from time import perf_counter
from typing import Any, Iterable

from src.shared import Emoji
from nonebot.rule import to_me
from src.core.auth import UserRole
from nonebot.matcher import Matcher
from nonebot import logger, on_message
from nonebot.adapters import Bot, Event
from src.platform.config import priority
from src.platform.session import EventSession
from src.core.skills import markdown_to_image_skill
from nonebot.adapters.qq.exception import ActionFailed
from src.platform.commands.registry import command_registry
from nonebot.adapters.onebot.v12.exception import NetworkError
from src.platform.commands.adapters import AgentCommandAdapter
from src.platform.commands.context import CommandExecutionContext
from nonebot_plugin_alconna import Target, UniMsg, MsgTarget, UniMessage
from src.core.agent.runtime.workflow import collect_observation_display_summaries
from src.core.agent.runtime.schema import AutoTask, AutoTaskList, CommandObservation
from src.core.agent.runtime import RuntimeContext, ChatSessionDepends, markdown_to_message

from . import commands
from .commands import clear_chat, __helpers__

auto_gpt = on_message(priority=priority * 10, block=True, rule=to_me())


def preview_text(text: str | None, limit: int = 160) -> str:
    """生成适合日志输出的短文本预览。"""

    if not text:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def normalize_user_roles(roles: Iterable[UserRole | str] | None) -> set[UserRole]:
    """把事件侧角色值转换成命令执行上下文使用的角色枚举。"""

    normalized: set[UserRole] = set()
    for role in roles or []:
        if isinstance(role, UserRole):
            normalized.add(role)
            continue
        try:
            normalized.add(UserRole(role))
        except ValueError:
            logger.warning(f'AutoGPT ignored unknown user role "{role}" while dispatching command')
    return normalized


def auto_task_params_to_service_dict(task: AutoTask) -> dict[str, Any]:
    """Convert AutoTask params into a dict for service-style command handlers."""

    spec = command_registry.get(task.command)
    text_params = [param for param in task.params if param.type == "text" and not param.separate]
    image_params = [param for param in task.params if param.type == "image" and not param.separate]
    payload: dict[str, Any] = {}

    if spec is not None:
        for index, command_param in enumerate(spec.params):
            if index >= len(text_params):
                break
            if command_param.multiple:
                payload[command_param.name] = [param.value for param in text_params[index:]]
                break
            payload[command_param.name] = text_params[index].value
    else:
        payload.update({f"arg{index}": param.value for index, param in enumerate(text_params)})

    if image_params:
        payload["images"] = [param.value for param in image_params]
    return payload


async def dispatch_auto_task(
    task: AutoTask,
    target: Target,
    trace_id: str = "",
    user_id: int | None = None,
    roles: Iterable[UserRole | str] | None = None,
    platform_id: str | None = None,
    channel_id: str | None = None,
    guild_id: str | None = None,
    platform_name: str | None = None,
) -> list[CommandObservation]:
    """通过统一服务执行器调度自动任务。

    Agent 只调用接入 `CommandExecutor` 的 service 命令，避免 matcher
    分支绕过结构化权限、结果回填和可观测指标。
    """

    command_params = [param for param in task.params if not param.separate]
    logger.info(f'AutoGPT trace "{trace_id}" dispatch command "{task.command}"')
    if any(param.separate for param in task.params):
        message = f"命令 `{task.command}` 包含需要单独投递的参数，Agent 只支持 service handler 结构化参数。"
        return [
            CommandObservation(
                trace_id=trace_id,
                command=task.command,
                source_type="command",
                tool_name=task.command,
                params=list(task.params),
                dispatch_type="unsupported_command",
                status="failed",
                success=False,
                message=message,
                display_summary=message,
                context_summary=message,
                outputs=[message],
                context_outputs=[message],
                next_actions=["explain_failure"],
                outputs_sent_to_user=False,
            )
        ]

    agent_adapter = AgentCommandAdapter()
    if not agent_adapter.can_execute(task.command):
        message = f"命令 `{task.command}` 尚未接入统一 service 执行器，Agent 无法调用该命令。"
        return [
            CommandObservation(
                trace_id=trace_id,
                command=task.command,
                source_type="command",
                tool_name=task.command,
                params=command_params,
                dispatch_type="unsupported_command",
                status="failed",
                success=False,
                message=message,
                display_summary=message,
                context_summary=message,
                outputs=[message],
                context_outputs=[message],
                next_actions=["explain_failure"],
                outputs_sent_to_user=False,
            )
        ]

    result = await agent_adapter.execute(
        task.command,
        params=auto_task_params_to_service_dict(task),
        context=CommandExecutionContext(
            user_id=user_id,
            roles=normalize_user_roles(roles),
            platform=platform_id or str(getattr(target, "adapter", "") or ""),
            channel_id=channel_id if not getattr(target, "private", False) else None,
            guild_id=guild_id,
            trace_id=trace_id,
            invoker="agent_workflow",
            extra={
                "dispatch": "autogpt",
                "target_platform": getattr(target, "platform", None),
                "platform_name": platform_name or "",
            },
        ),
    )
    message = result.summary or ("命令已通过统一执行器完成。" if result.success else "命令统一执行器调用失败。")
    return [
        CommandObservation(
            trace_id=trace_id,
            command=task.command,
            source_type="command",
            tool_name=task.command,
            params=command_params,
            dispatch_type="command",
            status="succeeded" if result.success else "failed",
            success=result.success,
            message=message,
            display_summary="\n".join(result.observation_outputs or result.visible_outputs) or message,
            context_summary="\n".join(result.observation_outputs) or message,
            outputs=result.visible_outputs,
            context_outputs=result.observation_outputs,
            next_actions=["answer"] if result.success else ["explain_failure"],
            outputs_sent_to_user=False,
        )
    ]


async def send_progress(matcher: Matcher, text: str) -> None:
    """发送 AutoGPT 阶段性进度反馈。"""

    logger.info(f'AutoGPT progress send queued text="{preview_text(text, limit=120)}"')
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
    platform: EventSession,
    chat_session: ChatSessionDepends,
):
    """处理当前命令或事件逻辑。"""
    if chat_session.lock:
        await matcher.finish(Emoji.error + "上一条消息还在处理中，我处理完后再接着看这条。")
    try:
        turn_result = await chat_session.send_message(
            message,
            progress_reporter=lambda text: send_progress(matcher, text),
            runtime_context=RuntimeContext(
                user_id=chat_session.user_id,
                platform=platform.platform,
                platform_name=platform.platform_name,
                channel_id=platform.channel_id,
                guild_id=platform.guild_id,
                message_id=str(getattr(event, "message_id", "") or ""),
            ),
        )
    except Exception as e:
        logger.exception(f'AutoGPT trace "{chat_session.last_trace_id}" failed: {e}')
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
        return

    logger.info(
        f'AutoGPT trace "{chat_session.last_trace_id}" plugin entry handling turn for '
        f"user={chat_session.user_id} platform={platform.platform} channel={platform.channel_id}"
    )
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
    elif auto_task.is_violation:
        await matcher.finish(chat_session.user_visible_initial_reply(turn_result) or auto_task.reply)

    initial_reply = chat_session.user_visible_initial_reply(turn_result)
    if initial_reply:
        try:
            reply_started = perf_counter()
            logger.info(
                f'AutoGPT trace "{chat_session.last_trace_id}" sending initial reply '
                f'len={len(initial_reply)} preview="{preview_text(initial_reply)}"'
            )
            # reply行数大于10时转成图片发送
            if initial_reply.count("\n") < 10:
                await matcher.send(await markdown_to_message(initial_reply).export(adapter=target.adapter, bot=bot))
            else:
                pic = UniMessage.image(raw=await markdown_to_image_skill.to_image(initial_reply)) + UniMessage.text(
                    "文字太长已转为图片发送"
                )
                await matcher.send(await pic.export(adapter=target.adapter, bot=bot))
            logger.info(
                f'AutoGPT trace "{chat_session.last_trace_id}" sent initial reply '
                f"in {perf_counter() - reply_started:.3f}s"
            )
        except ActionFailed as e:
            logger.exception(e)
            await matcher.finish(Emoji.error + (e.message or str(e.status_code)))
        except NetworkError as e:
            logger.exception(e)
            await matcher.finish(Emoji.error + "内部异常, 请重试！")
    if not auto_task.need_confirm:
        workflow = turn_result.workflow if turn_result else None
        if workflow and workflow.steps:
            workflow_started = perf_counter()
            logger.info(
                f'AutoGPT trace "{chat_session.last_trace_id}" starting workflow execution '
                f"kind={workflow.kind} status={workflow.status} steps={len(workflow.steps)}"
            )
            execution = await chat_session.execute_task_workflow(
                workflow,
                dispatcher=lambda task: dispatch_auto_task(
                    task,
                    target,
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
            if execution.final_reply:
                user_message = (
                    Emoji.error + execution.final_reply
                    if execution.workflow.status == "failed"
                    else execution.final_reply
                )
                send_started = perf_counter()
                logger.info(
                    f'AutoGPT trace "{chat_session.last_trace_id}" sending execution final reply '
                    f'len={len(user_message)} preview="{preview_text(user_message)}"'
                )
                await matcher.send(await markdown_to_message(user_message).export(adapter=target.adapter, bot=bot))
                logger.info(
                    f'AutoGPT trace "{chat_session.last_trace_id}" sent execution final reply '
                    f"in {perf_counter() - send_started:.3f}s"
                )
        elif workflow:
            logger.info(
                f'AutoGPT trace "{chat_session.last_trace_id}" skipped workflow execution because no steps were generated '
                f"kind={workflow.kind} status={workflow.status}"
            )
        else:
            observations: list[CommandObservation] = []
            for task in auto_task.tasks:
                if chat_session.helpers.get_helper(task.command):
                    observations.extend(
                        await dispatch_auto_task(
                            task,
                            target,
                            trace_id=chat_session.last_trace_id,
                            user_id=chat_session.user_id,
                            roles=chat_session.helpers.active_roles,
                            platform_id=platform.platform,
                            channel_id=platform.channel_id,
                            guild_id=platform.guild_id,
                            platform_name=platform.platform_name,
                        )
                    )
                else:
                    observations.append(
                        CommandObservation(
                            trace_id=chat_session.last_trace_id,
                            command=task.command,
                            source_type="command",
                            tool_name=task.command,
                            params=task.params,
                            dispatch_type="missing_command",
                            status="failed",
                            success=False,
                            message="命令不存在，未投递。",
                            display_summary="命令不存在，未投递。",
                            context_summary="命令不存在，未投递。",
                            next_actions=["explain_failure"],
                        )
                    )
                    await matcher.send(Emoji.error + f"无法调用`{task.command}`命令，因为该命令不存在！")
            if observations:
                chat_session.record_observations(observations, trace_id=chat_session.last_trace_id)
                executed_count = sum(1 for observation in observations if observation.dispatch_type == "command")
                if executed_count:
                    await matcher.send(
                        await markdown_to_message(f"已运行 {executed_count} 条命令。").export(
                            adapter=target.adapter,
                            bot=bot,
                        )
                    )
                display_summaries = collect_observation_display_summaries(observations)
                if display_summaries:
                    await matcher.send(
                        await markdown_to_message("\n\n".join(display_summaries)).export(
                            adapter=target.adapter,
                            bot=bot,
                        )
                    )
