from __future__ import annotations

from inspect import _empty, stack
from typing import Any

from nonebot.adapters import Bot, Event
from arclet.alconna import Alconna
from arclet.alconna.typing import MultiVar
from pydantic import BaseModel, Field
from src.core.auth import UserRole
from src.platform.helper import Context, ParamMode, HelperScope

from .schema import CommandExecutionMode, CommandParam, CommandRiskLevel
from .spec import CommandSpec
from .registry import command_registry
from .executor import CommandHandler, command_executor
from .history import dispatch_command_input_recorders
from .renderers.helper import command_spec_to_helper


class CommandBinding(BaseModel):
    """补充 Alconna 无法完整表达的项目级命令元数据。"""

    description: str | None = None
    ai_description: str = ""
    roles: set[UserRole] = Field(default_factory=set)
    exclude_roles: set[UserRole] = Field(default_factory=set)
    scopes: set[HelperScope] = Field(default_factory=set)
    tags: set[str] = Field(default_factory=set)
    examples: list[Context] = Field(default_factory=list)
    params: list[CommandParam] | None = None
    param_labels: dict[str, str] = Field(default_factory=dict)
    param_descriptions: dict[str, str] = Field(default_factory=dict)
    risk_level: CommandRiskLevel = "low"
    agent_callable: bool = True
    execution_mode: CommandExecutionMode = "matcher"
    plugin_module: str | None = None
    helper_visible: bool = True


def command_alconna(alconna: Alconna, *, binding: CommandBinding | None = None, aliases=None, **kwargs):
    """创建 Alconna matcher 并绑定统一命令元数据。

    Args:
        alconna: Alconna 命令声明对象。
        binding: 项目级命令元数据，包含权限、目录、风险等级等。
        aliases: 命令别名，语义与 ``on_alconna`` 保持一致。
        **kwargs: 继续透传给 ``nonebot_plugin_alconna.on_alconna``。

    Returns:
        type[Matcher]: 已绑定 ``CommandSpec`` 和 ``Helper`` 的 matcher。
    """

    from nonebot_plugin_alconna import on_alconna

    caller_module = _caller_module_name()
    matcher = on_alconna(alconna, aliases=aliases, **kwargs)
    _apply_matcher_module(matcher, caller_module)
    spec = spec_from_alconna(
        alconna,
        binding=_with_default_plugin(binding, caller_module),
        aliases=_normalize_aliases(aliases),
    )
    _bind_spec_to_matcher(matcher, spec)
    _bind_command_history_recorder(matcher, spec)
    return matcher


def command_command(command: str, *, binding: CommandBinding | None = None, aliases=None, **kwargs):
    """创建普通 NoneBot 命令 matcher 并绑定统一命令元数据。

    该包装器主要用于简单命令或确实不适合 Alconna 的特殊入口。

    Args:
        command: 主命令名称。
        binding: 项目级命令元数据。
        aliases: 命令别名，语义与 ``on_command`` 保持一致。
        **kwargs: 继续透传给 ``nonebot.on_command``。

    Returns:
        type[Matcher]: 已绑定 ``CommandSpec`` 和 ``Helper`` 的 matcher。
    """

    from nonebot import on_command

    caller_module = _caller_module_name()
    matcher = on_command(command, aliases=aliases, **kwargs)
    _apply_matcher_module(matcher, caller_module)
    spec = spec_from_command(
        command,
        binding=_with_default_plugin(binding, caller_module),
        aliases=_normalize_aliases(aliases),
    )
    _bind_spec_to_matcher(matcher, spec)
    _bind_command_history_recorder(matcher, spec)
    return matcher


def on_agent_command(
    command: Alconna | str,
    *,
    binding: CommandBinding | None = None,
    aliases=None,
    service_handler: CommandHandler | None = None,
    **kwargs,
):
    """创建同时服务用户命令、帮助菜单和 Agent 工具目录的统一命令。

    该入口是 ``command_alconna`` 和 ``command_command`` 的项目级门面：
    传入 ``Alconna`` 时复用 Alconna matcher，传入字符串时复用 NoneBot
    ``on_command``。无论哪种方式，都会生成 ``CommandSpec``、``Helper``、
    命令注册表元数据和命令输入记录器。若提供 ``service_handler``，还会
    注册到统一 ``CommandExecutor``，供 Agent 工作流直接调用。

    Args:
        command: Alconna 命令对象或普通命令名称。
        binding: 项目级命令元数据。
        aliases: 命令别名。
        service_handler: 可选的 service-style 执行函数。
        **kwargs: 继续透传给底层 matcher 创建函数。

    Returns:
        type[Matcher]: 已融合 NoneBot、Helper、注册表和 Agent 执行能力的 matcher。
    """

    binding = _binding_for_agent_command(binding, service_handler)
    if isinstance(command, Alconna):
        matcher = command_alconna(command, binding=binding, aliases=aliases, **kwargs)
    else:
        matcher = command_command(str(command), binding=binding, aliases=aliases, **kwargs)

    if service_handler is not None:
        _register_agent_handler(matcher, service_handler)
    _attach_agent_handler_decorator(matcher)
    return matcher


def spec_from_alconna(
    alconna: Alconna,
    *,
    binding: CommandBinding | None = None,
    aliases: set[str] | None = None,
) -> CommandSpec:
    """从 Alconna 命令对象构建统一命令元数据。

    Args:
        alconna: Alconna 命令声明对象。
        binding: 项目级命令元数据。
        aliases: 已归一化后的命令别名集合。

    Returns:
        CommandSpec: 可用于 Helper、Agent tool 和管理端目录的命令元数据。
    """

    binding = binding or CommandBinding()
    meta = getattr(alconna, "meta", None)
    description = binding.description or _meta_text(meta, "description") or str(alconna.command)
    examples = list(binding.examples)
    example_text = _meta_text(meta, "example")
    if example_text and not examples:
        examples.append(Context(rote="用户", content=example_text))

    return CommandSpec(
        name=str(alconna.command),
        aliases=set(aliases or ()),
        description=description,
        ai_description=binding.ai_description,
        params=list(binding.params) if binding.params is not None else _params_from_alconna(alconna, binding),
        roles=set(binding.roles),
        exclude_roles=set(binding.exclude_roles),
        scopes=set(binding.scopes),
        tags=set(binding.tags),
        examples=examples,
        risk_level=binding.risk_level,
        agent_callable=binding.agent_callable,
        execution_mode=binding.execution_mode,
        plugin_module=binding.plugin_module,
        helper_visible=binding.helper_visible,
    )


def spec_from_command(
    command: str,
    *,
    binding: CommandBinding | None = None,
    aliases: set[str] | None = None,
) -> CommandSpec:
    """为普通 ``on_command`` 命令构建统一命令元数据。

    Args:
        command: 主命令名称。
        binding: 项目级命令元数据。
        aliases: 已归一化后的命令别名集合。

    Returns:
        CommandSpec: 普通命令对应的命令元数据。
    """

    binding = binding or CommandBinding()
    return CommandSpec(
        name=command,
        aliases=set(aliases or ()),
        description=binding.description or command,
        ai_description=binding.ai_description,
        params=list(binding.params or []),
        roles=set(binding.roles),
        exclude_roles=set(binding.exclude_roles),
        scopes=set(binding.scopes),
        tags=set(binding.tags),
        examples=list(binding.examples),
        risk_level=binding.risk_level,
        agent_callable=binding.agent_callable,
        execution_mode=binding.execution_mode,
        plugin_module=binding.plugin_module,
        helper_visible=binding.helper_visible,
    )


def _bind_spec_to_matcher(matcher, spec: CommandSpec) -> None:
    """将命令元数据挂载到 matcher，并注册到全局命令注册表。

    Args:
        matcher: NoneBot matcher 类型对象。
        spec: 待绑定的命令元数据。
    """

    command_registry.register(spec)
    matcher.__command_spec__ = spec
    if spec.helper_visible:
        helper = command_spec_to_helper(spec)
        matcher.__helper__ = helper
        matcher.__helper_command__ = helper.command


def _bind_command_history_recorder(matcher, spec: CommandSpec) -> None:
    """为命令 matcher 挂载输入记录器。

    Args:
        matcher: NoneBot matcher 类型对象。
        spec: 当前 matcher 对应的命令元数据。
    """

    if spec.execution_mode == "interactive":
        return

    async def record_command_input(bot: Bot, event: Event) -> None:
        """在命令业务处理前记录用户输入。"""

        if not _event_looks_like_command_trigger(event, spec):
            return
        await dispatch_command_input_recorders(bot, event, spec)

    record_command_input.__name__ = f"record_command_input_{id(spec)}"
    matcher.handle()(record_command_input)


def _binding_for_agent_command(
    binding: CommandBinding | None,
    service_handler: CommandHandler | None,
) -> CommandBinding:
    """根据统一命令入口语义补齐绑定配置。

    Args:
        binding: 调用方传入的绑定元数据。
        service_handler: 可选的 service-style 执行函数。

    Returns:
        CommandBinding: 适合统一命令入口使用的绑定元数据。
    """

    binding = binding or CommandBinding()
    if service_handler is None or binding.execution_mode != "matcher":
        return binding
    return binding.copy(update={"execution_mode": "service"})


def _attach_agent_handler_decorator(matcher) -> None:
    """在 matcher 上挂载 ``agent_handler`` 装饰器。

    Args:
        matcher: 已绑定 ``CommandSpec`` 的 matcher。
    """

    if hasattr(matcher, "agent_handler"):
        return

    def agent_handler(handler: CommandHandler) -> CommandHandler:
        """注册当前命令的 service-style Agent 执行函数。"""

        return _register_agent_handler(matcher, handler)

    matcher.agent_handler = agent_handler


def _register_agent_handler(matcher, handler: CommandHandler) -> CommandHandler:
    """把 matcher 绑定的命令注册到统一执行器。

    Args:
        matcher: 已绑定 ``CommandSpec`` 的 matcher。
        handler: service-style 执行函数。

    Returns:
        CommandHandler: 原始处理函数，便于装饰器保持函数引用。

    Raises:
        RuntimeError: matcher 尚未绑定 ``CommandSpec``。
    """

    spec: CommandSpec | None = getattr(matcher, "__command_spec__", None)
    if spec is None:
        raise RuntimeError("on_agent_command 只能为已绑定 CommandSpec 的 matcher 注册 Agent handler。")
    if spec.execution_mode == "matcher":
        spec.execution_mode = "service"
    command_executor.register(spec.name, handler)
    return handler


def _event_looks_like_command_trigger(event: Event, spec: CommandSpec) -> bool:
    """判断当前事件文本是否像该命令的首条触发消息。

    多轮交互命令在 `got` / `receive` 阶段收到的确认消息，例如 `yes`、`no`
    或附件补充消息，不应再次按“命令输入”写入聊天记录，否则会干扰交互态
    matcher 的执行边界。

    Args:
        event: 当前平台事件。
        spec: 当前 matcher 对应的命令元数据。

    Returns:
        bool: 看起来是首条命令触发消息时返回 ``True``。
    """

    get_plaintext = getattr(event, "get_plaintext", None)
    if not callable(get_plaintext):
        return False

    text = " ".join(str(get_plaintext() or "").split())
    if not text:
        return False

    for command_name in sorted(spec.commands, key=len, reverse=True):
        candidate = " ".join(str(command_name).split())
        if not candidate:
            continue
        if text == candidate:
            return True
        if text.startswith(candidate) and len(text) > len(candidate) and text[len(candidate)].isspace():
            return True
    return False


def _params_from_alconna(alconna: Alconna, binding: CommandBinding) -> list[CommandParam]:
    """从 Alconna 参数定义中提取统一参数元数据。

    Args:
        alconna: Alconna 命令声明对象。
        binding: 项目级命令元数据，用于补充参数中文名和描述。

    Returns:
        list[CommandParam]: 提取出的参数元数据列表。
    """

    params: list[CommandParam] = []
    for arg in getattr(alconna, "args", []):
        source_name = str(arg.name)
        name = binding.param_labels.get(source_name, source_name)
        mode, multiple = _param_mode_and_multiple(arg)
        params.append(
            CommandParam(
                name=name,
                description=binding.param_descriptions.get(source_name, ""),
                mode=mode,
                value_type=_value_type(getattr(arg, "value", None)),
                multiple=multiple,
                source_name=source_name,
            )
        )
    return params


def _param_mode_and_multiple(arg) -> tuple[ParamMode | None, bool]:
    """根据 Alconna 参数对象推断 Helper 参数数量模式。

    Args:
        arg: Alconna 参数对象。

    Returns:
        tuple[ParamMode | None, bool]: 参数数量模式，以及是否为多值参数。
    """

    value = getattr(arg, "value", None)
    if isinstance(value, MultiVar):
        if value.flag == "+":
            return ParamMode.ONE_OR_MORE, True
        if value.flag == "*":
            return ParamMode.ZERO_OR_MORE, True
    if getattr(arg, "optional", False) or getattr(getattr(arg, "field", None), "default", _empty) is not _empty:
        return ParamMode.OPTIONAL, False
    return None, False


def _value_type(value: Any) -> str:
    """把 Alconna 参数类型映射成 JSON Schema 基础类型。

    Args:
        value: Alconna 参数类型定义。

    Returns:
        str: ``string``、``integer``、``number`` 或 ``boolean``。
    """

    if isinstance(value, MultiVar):
        value = value.base
    value_text = str(value)
    if "int" in value_text:
        return "integer"
    if "float" in value_text:
        return "number"
    if "bool" in value_text:
        return "boolean"
    return "string"


def _meta_text(meta: Any, field_name: str) -> str:
    """读取 Alconna ``CommandMeta`` 中的非空文本字段。

    Args:
        meta: Alconna 命令元数据对象。
        field_name: 字段名称。

    Returns:
        str: 读取到的文本；字段为空或为默认值时返回空字符串。
    """

    value = getattr(meta, field_name, None)
    if not value or value == "Unknown":
        return ""
    return str(value)


def _normalize_aliases(aliases) -> set[str]:
    """将 NoneBot 别名参数统一转换成字符串集合。

    Args:
        aliases: ``None``、字符串或可迭代别名集合。

    Returns:
        set[str]: 归一化后的别名集合。
    """

    if aliases is None:
        return set()
    if isinstance(aliases, str):
        return {aliases}
    return {str(alias) for alias in aliases}


def _with_default_plugin(binding: CommandBinding | None, module_name: str | None = None) -> CommandBinding:
    """在未显式配置时根据调用方模块补齐插件模块名。

    Args:
        binding: 原始命令绑定元数据。
        module_name: 调用方模块名。

    Returns:
        CommandBinding: 补齐 ``plugin_module`` 后的绑定元数据。
    """

    binding = binding or CommandBinding()
    if binding.plugin_module:
        return binding
    inferred_module = module_name or _caller_module_name() or ""
    return binding.copy(update={"plugin_module": _plugin_module_from_module_name(inferred_module)})


def _caller_module_name() -> str | None:
    """从调用栈中推断第一个非 ``src.platform.commands`` 模块名。

    Returns:
        str | None: 调用方模块名；无法推断时返回 ``None``。
    """

    for frame_info in stack()[2:]:
        module_name = frame_info.frame.f_globals.get("__name__")
        if not isinstance(module_name, str):
            continue
        if module_name.startswith("src.platform.commands"):
            continue
        return module_name
    return None


def _plugin_module_from_module_name(module_name: str) -> str:
    """将业务子模块名折叠成插件模块名。

    Args:
        module_name: Python 模块名，例如 ``src.plugins.application.active.user.commands``。

    Returns:
        str: 插件模块名，例如 ``src.plugins.application.active.user``。
    """

    parts = module_name.split(".")
    if len(parts) >= 3 and parts[0] == "src" and parts[1] == "features":
        return ".".join(parts[:3])
    return module_name


def _apply_matcher_module(matcher, module_name: str | None) -> None:
    """修正包装器隐藏掉的 matcher 业务模块归属。

    Args:
        matcher: NoneBot matcher 类型对象。
        module_name: 真实业务模块名。
    """

    if module_name:
        matcher.module_name = module_name
