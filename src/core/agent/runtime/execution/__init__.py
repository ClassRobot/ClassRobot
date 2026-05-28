"""Unified action execution contracts."""

from .actions import ActionResult, ActionRequest, ActionExecutor, ActionExecutorRegistry
from .command_dispatcher import dispatch_auto_task, dispatch_auto_tasks, auto_task_params_to_service_dict

__all__ = [
    "ActionExecutor",
    "ActionExecutorRegistry",
    "ActionRequest",
    "ActionResult",
    "auto_task_params_to_service_dict",
    "dispatch_auto_task",
    "dispatch_auto_tasks",
]
