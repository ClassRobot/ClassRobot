from __future__ import annotations

from typing import Any
from collections.abc import Iterable

from nonebot import logger
from src.core.auth import UserRole
from src.platform.helper import Helpers
from src.platform.commands.cli import command_cli
from src.platform.commands.registry import command_registry
from src.platform.commands.context import CommandExecutionContext, normalize_user_roles

from ..schema import AutoTask, CommandObservation


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
            source_name = command_param.source_name or command_param.name
            if command_param.multiple:
                value = [param.value for param in text_params[index:]]
                payload[command_param.name] = value
                if source_name != command_param.name:
                    payload[source_name] = value
                break
            value = command_cli.coerce_value(text_params[index].value, command_param.value_type)
            payload[command_param.name] = value
            if source_name != command_param.name:
                payload[source_name] = value
    else:
        payload.update({f"arg{index}": param.value for index, param in enumerate(text_params)})

    if image_params:
        payload["images"] = [param.value for param in image_params]
    return payload


async def dispatch_auto_task(
    task: AutoTask,
    trace_id: str = "",
    user_id: int | None = None,
    roles: Iterable[UserRole | str] | None = None,
    platform_id: str | None = None,
    channel_id: str | None = None,
    guild_id: str | None = None,
    platform_name: str | None = None,
) -> list[CommandObservation]:
    """通过统一 service 执行器调度 Agent 自动任务。"""

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

    if not command_cli.executor.has_handler(task.command):
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

    result = await command_cli.run_command(
        task.command,
        params=auto_task_params_to_service_dict(task),
        context=CommandExecutionContext(
            user_id=user_id,
            roles=normalize_user_roles(list(roles or [])),
            platform=platform_id or "",
            channel_id=channel_id,
            guild_id=guild_id,
            trace_id=trace_id,
            invoker="agent_workflow",
            extra={
                "dispatch": "autogpt",
                "platform_name": platform_name or "",
            },
        ),
    )
    message = result.summary or ("命令已通过统一执行器完成。" if result.success else "命令统一执行器调用失败。")
    observations = [
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
            raw_result=result.model_dump(),
            next_actions=["answer"] if result.success else ["explain_failure"],
            outputs_sent_to_user=False,
        )
    ]
    _emit_command_observation_trace(trace_id, task.command, result)
    return observations


async def dispatch_auto_tasks(
    tasks: list[AutoTask],
    *,
    helpers: Helpers,
    trace_id: str = "",
    user_id: int | None = None,
    roles: Iterable[UserRole | str] | None = None,
    platform_id: str | None = None,
    channel_id: str | None = None,
    guild_id: str | None = None,
    platform_name: str | None = None,
) -> list[CommandObservation]:
    """批量调度 legacy AutoTask，并把可见性失败转换为 observation。"""

    observations: list[CommandObservation] = []
    for task in tasks:
        if helpers.get_helper(task.command):
            observations.extend(
                await dispatch_auto_task(
                    task,
                    trace_id=trace_id,
                    user_id=user_id,
                    roles=roles,
                    platform_id=platform_id,
                    channel_id=channel_id,
                    guild_id=guild_id,
                    platform_name=platform_name,
                )
            )
            continue
        observations.append(
            CommandObservation(
                trace_id=trace_id,
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
                outputs_sent_to_user=False,
            )
        )
    return observations


def _emit_command_observation_trace(trace_id: str, command: str, result) -> None:
    """记录 Agent command 执行结果已经转换为 observation。"""

    if not trace_id:
        return
    try:
        from src.core.agent.runtime.live_trace import agent_live_trace_registry
    except Exception:
        return

    agent_live_trace_registry.emit(
        trace_id,
        event_type="observation_recorded",
        stage="loop",
        node_type="command_observation",
        node_label=command,
        status="completed" if result.success else "failed",
        tool_name=command,
        params_preview={
            "success": result.success,
            "summary": result.summary,
            "visible_outputs": result.visible_outputs,
            "context_outputs": result.context_outputs,
            "data": result.data,
        },
        observation_summary="\n".join(result.observation_outputs) or result.summary,
    )
