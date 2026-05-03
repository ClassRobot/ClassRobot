import re
from types import ModuleType
from typing import Any, Iterable

from nonebot import logger
from nonebot.dependencies import Dependent
from nonebot.matcher import Matcher
from nonebot.plugin import Plugin
from nonebot.internal.matcher.matcher import MatcherMeta

from .config import helper_menu
from .schema import Helper


def _extract_rule_literals(matcher: type[Matcher]) -> set[str]:
    """从 matcher 规则字符串中提取字面量命令。"""

    rule_text = str(getattr(matcher, "rule", ""))
    return {item.strip() for item in re.findall(r"\('([^']+)',\)", rule_text) if item.strip()}


def extract_matcher_commands(matcher: type[Matcher]) -> set[str]:
    """提取 matcher 可触发的主命令与别名。"""

    commands = _extract_rule_literals(matcher)
    command_path = getattr(matcher, "_command_path", "")
    if isinstance(command_path, str) and command_path:
        commands.add(command_path.split("::", 1)[-1].strip())
    return {command for command in commands if command}


def iter_module_matchers(module: ModuleType) -> Iterable[type[Matcher]]:
    """遍历模块内直接声明的 matcher。"""

    for value in vars(module).values():
        if not isinstance(value, MatcherMeta):
            continue
        if getattr(value, "module_name", None) != module.__name__:
            continue
        if extract_matcher_commands(value):
            yield value


def _prepend_handler(matcher: type[Matcher], handler) -> None:
    """把鉴权处理器插入到 matcher 处理链最前面。"""

    dependent = Dependent[Any].parse(call=handler, allow_types=matcher.HANDLER_PARAM_TYPES)
    matcher.handlers.insert(0, dependent)


def bind_helper_access_guard(matcher: type[Matcher], helper: Helper) -> None:
    """为 matcher 绑定基于 Helper 元数据的统一鉴权前置处理器。"""

    if getattr(matcher, "__helper_access_bound__", False):
        return

    from utils.models.depends import UserOrCreatedDepends

    async def _guard(runtime_matcher: Matcher, user: UserOrCreatedDepends, __helper: Helper = helper):
        if __helper.is_available_for(*user.roles):
            return
        await runtime_matcher.finish(f"您当前身份暂无权限使用“{__helper.command}”命令。")

    _prepend_handler(matcher, _guard)
    matcher.__helper_access_bound__ = True
    matcher.__helper_command__ = helper.command


def bind_module_helpers(module: ModuleType, helpers: Iterable[Helper]) -> None:
    """根据模块中的 Helper 元数据为匹配器绑定统一鉴权。"""

    command_map: dict[str, Helper] = {}
    for helper in helpers:
        for command in helper.commands:
            command_map[command] = helper

    for matcher in iter_module_matchers(module):
        matcher_commands = extract_matcher_commands(matcher)
        matched_helper = next((command_map[name] for name in matcher_commands if name in command_map), None)
        if matched_helper is None:
            continue
        bind_helper_access_guard(matcher, matched_helper)


def bootstrap_helper_runtime(plugins: Iterable[Plugin]) -> None:
    """重建帮助目录，并把帮助元数据同步绑定到命令鉴权链路。"""

    helper_menu.clear()

    for plugin in plugins:
        for module in filter(None, (plugin.module, getattr(plugin.module, "commands", None))):
            helpers = getattr(module, "__helpers__", None)
            if not helpers:
                continue
            helper_menu.extend(helpers)
            bind_module_helpers(module, helpers)

    logger.info("helper runtime bootstrapped with %s helpers", len(helper_menu.helpers))
