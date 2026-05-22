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

    from src.models.depends import UserOrCreatedDepends
    from src.platform.commands.availability import command_availability
    from src.platform.commands.context import CommandExecutionContext
    from src.platform.commands.policy import command_policy

    async def _guard(runtime_matcher: Matcher, user: UserOrCreatedDepends, __helper: Helper = helper):
        spec = getattr(runtime_matcher, "__command_spec__", None)
        if spec is not None:
            context = CommandExecutionContext(user_id=user.id, roles=set(user.roles), invoker="user_command")
            decision = command_policy.check(spec, context)
            if decision.allowed:
                return
            await runtime_matcher.finish(f"您当前无法使用“{__helper.command}”命令：{decision.reason}")

        availability = command_availability.check(None, __helper.command)
        if not availability.available:
            await runtime_matcher.finish(f"“{__helper.command}”命令当前不可用：{availability.reason}")

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


def collect_bound_helpers(module: ModuleType) -> list[Helper]:
    """Collect helpers that are directly attached to matcher objects."""

    helpers: list[Helper] = []
    seen_commands: set[str] = set()
    for matcher in iter_module_matchers(module):
        helper = getattr(matcher, "__helper__", None)
        if not isinstance(helper, Helper):
            continue
        if helper.command in seen_commands:
            continue
        seen_commands.add(helper.command)
        helpers.append(helper)
        bind_helper_access_guard(matcher, helper)
    return helpers


def merge_helpers(*helper_groups: Iterable[Helper]) -> list[Helper]:
    """Merge helper groups while keeping the first definition for each command."""

    helpers: list[Helper] = []
    seen_commands: set[str] = set()
    for group in helper_groups:
        for helper in group:
            if helper.command in seen_commands:
                continue
            seen_commands.add(helper.command)
            helpers.append(helper)
    return helpers


def bootstrap_helper_runtime(plugins: Iterable[Plugin]) -> None:
    """重建帮助目录，并把帮助元数据同步绑定到命令鉴权链路。"""

    helper_menu.clear()

    for plugin in plugins:
        for module in filter(None, (plugin.module, getattr(plugin.module, "commands", None))):
            bound_helpers = collect_bound_helpers(module)
            manual_helpers = getattr(module, "__helpers__", None) or []
            helpers = merge_helpers(bound_helpers, manual_helpers)
            if not helpers:
                continue
            helper_menu.extend(helpers)
            if manual_helpers:
                bind_module_helpers(module, manual_helpers)

    logger.info("helper runtime bootstrapped with {} helpers", len(helper_menu.helpers))
