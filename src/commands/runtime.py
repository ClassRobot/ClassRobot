from __future__ import annotations

from nonebot import get_loaded_plugins

from utils.helper.runtime import bootstrap_helper_runtime


def bootstrap_command_runtime() -> None:
    """Bootstrap helper guards and command-derived helper views."""

    bootstrap_helper_runtime(get_loaded_plugins())
