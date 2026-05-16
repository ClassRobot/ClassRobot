import sys
from importlib import import_module
from typing import Any, Iterable

from nonebot.rule import to_me
from nonebot.matcher import Matcher
from nonebot import logger, on_command, on_message
from utils.commands.registry import command_registry
from src.agents.skills import markdown_to_image_skill
from utils.commands.adapters import AgentCommandAdapter
from nonebot.adapters.qq.exception import ActionFailed
from utils.commands.context import CommandExecutionContext
from nonebot.adapters.onebot.v12.exception import NetworkError
from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import Target, UniMsg, MsgTarget, UniMessage

from utils import Emoji
from utils.roles import UserRole
from utils.config import priority
from utils.session import EventSession
from utils.helper import Helper, HelperScope
from core.agent.runtime import ChatSessionDepends, RuntimeContext, markdown_to_message
from core.agent.runtime.workflow import (
    collect_unsent_observation_outputs,
)
from core.agent.runtime.schema import AutoTask, AutoTaskList, CommandObservation, Param

auto_gpt = on_message(priority=priority * 10, block=True, rule=to_me())
clear_chat = on_command("清空聊天", aliases={"重置聊天", "聊天清空", "聊天重置"}, priority=priority, block=True)


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
                params=list(task.params),
                dispatch_type="unsupported_command",
                success=False,
                message=message,
                outputs=[message],
                context_outputs=[message],
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
                params=command_params,
                dispatch_type="unsupported_command",
                success=False,
                message=message,
                outputs=[message],
                context_outputs=[message],
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
            params=command_params,
            dispatch_type="command",
            success=result.success,
            message=message,
            outputs=result.visible_outputs,
            context_outputs=result.observation_outputs,
            outputs_sent_to_user=False,
        )
    ]


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
    platform: EventSession,
    chat_session: ChatSessionDepends,
):
    """处理当前命令或事件逻辑。"""
    if chat_session.lock:
        await matcher.finish(Emoji.error + "我知道你很急，但是你先别急，等我处理完你的上一条消息。")
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

    auto_task = turn_result.auto_tasks if turn_result else None
    if turn_result and turn_result.workflow and auto_task and auto_task.need_confirm:
        await chat_session.record_workflow(turn_result.workflow, trace_id=chat_session.last_trace_id)

    if not isinstance(auto_task, AutoTaskList):
        await matcher.finish(Emoji.error + "消息理解失败了, 请重新发送")
        return
    elif auto_task.is_violation:
        await matcher.finish(auto_task.reply)

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
            )
            if execution.final_reply:
                user_message = (
                    Emoji.error + execution.final_reply
                    if execution.workflow.status == "failed"
                    else execution.final_reply
                )
                await matcher.send(await markdown_to_message(user_message).export(adapter=target.adapter, bot=bot))
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
                            params=task.params,
                            dispatch_type="missing_command",
                            success=False,
                            message="命令不存在，未投递。",
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
                unsent_outputs = collect_unsent_observation_outputs(observations)
                if unsent_outputs:
                    await matcher.send(
                        await markdown_to_message("\n\n".join(unsent_outputs)).export(adapter=target.adapter, bot=bot)
                    )


__helpers__ = [
    Helper(
        command="清空聊天",
        description="清空机器人于用户的聊天内容",
        roles={UserRole.user},
        scopes={HelperScope.user},
        ai_description="当用户对于机器人的回复非常不满意，或者存在违规内容时候机器人可以主动清空聊天记录",
    )
]

LEGACY_RUNTIME_MODULE_ALIASES = {
    "src.plugins.autogpt.checkpoints": "core.agent.runtime.checkpoints",
    "src.plugins.autogpt.command_tools": "core.agent.runtime.command_tools",
    "src.plugins.autogpt.coordination": "core.agent.runtime.coordination",
    "src.plugins.autogpt.coordination.local_context": "core.agent.runtime.coordination.local_context",
    "src.plugins.autogpt.coordination.nodes": "core.agent.runtime.coordination.nodes",
    "src.plugins.autogpt.coordination.state": "core.agent.runtime.coordination.state",
    "src.plugins.autogpt.exception": "core.agent.runtime.exception",
    "src.plugins.autogpt.graph_executor": "core.agent.runtime.graph_executor",
    "src.plugins.autogpt.harness": "core.agent.runtime.harness",
    "src.plugins.autogpt.harness.context": "core.agent.runtime.harness.context",
    "src.plugins.autogpt.harness.observability": "core.agent.runtime.harness.observability",
    "src.plugins.autogpt.harness.policy": "core.agent.runtime.harness.policy",
    "src.plugins.autogpt.harness.runtime": "core.agent.runtime.harness.runtime",
    "src.plugins.autogpt.knowledge": "core.agent.runtime.knowledge",
    "src.plugins.autogpt.node_registry": "core.agent.runtime.node_registry",
    "src.plugins.autogpt.orchestration_config": "core.agent.runtime.orchestration_config",
    "src.plugins.autogpt.persistence": "core.agent.runtime.persistence",
    "src.plugins.autogpt.persistence.checkpoints": "core.agent.runtime.persistence.checkpoints",
    "src.plugins.autogpt.persistence.runs": "core.agent.runtime.persistence.runs",
    "src.plugins.autogpt.pipeline": "core.agent.runtime.pipeline",
    "src.plugins.autogpt.playbooks": "core.agent.runtime.playbooks",
    "src.plugins.autogpt.prompt_selection": "core.agent.runtime.prompt_selection",
    "src.plugins.autogpt.runs": "core.agent.runtime.runs",
    "src.plugins.autogpt.schema": "core.agent.runtime.schema",
    "src.plugins.autogpt.util": "core.agent.runtime.util",
    "src.plugins.autogpt.workflow": "core.agent.runtime.workflow",
}


def register_legacy_runtime_aliases() -> None:
    """把旧的 `src.plugins.autogpt.*` 运行时路径映射到 `core.agent.runtime.*`。"""

    package = sys.modules[__name__]
    for legacy_name, target_name in LEGACY_RUNTIME_MODULE_ALIASES.items():
        target_module = import_module(target_name)
        sys.modules[legacy_name] = target_module
    setattr(package, "coordination", sys.modules["src.plugins.autogpt.coordination"])
    setattr(package, "harness", sys.modules["src.plugins.autogpt.harness"])
    setattr(package, "persistence", sys.modules["src.plugins.autogpt.persistence"])


register_legacy_runtime_aliases()
