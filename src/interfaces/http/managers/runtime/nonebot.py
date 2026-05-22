from __future__ import annotations

import ast
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from nonebot import get_adapters, get_bots, get_driver, get_loaded_plugins

from src.platform.config import project_root

from .command_state import load_availability_state
from ..service import relative_to_project

PYPROJECT_PATH = project_root / "pyproject.toml"
SOURCE_ROOTS = (
    project_root / "src" / "plugins" / "application" / "active",
    project_root / "src" / "plugins" / "application" / "passive",
    project_root / "src" / "plugins" / "library",
)


def get_nonebot_overview() -> dict[str, Any]:
    """汇总 NoneBot 运行时、插件、命令、适配器和 Bot 信息。

    Returns:
        dict[str, Any]: 面向管理端总览页的只读运行时清单。
    """

    load_availability_state()
    commands_payload = list_commands()
    commands = commands_payload["items"]
    plugins_payload = list_plugins(commands)
    adapters_payload = list_adapters()
    bots_payload = list_bots()
    runtime = get_runtime_info()

    errors = [
        *runtime.get("errors", []),
        *plugins_payload.get("errors", []),
        *adapters_payload.get("errors", []),
        *bots_payload.get("errors", []),
        *commands_payload.get("errors", []),
    ]
    adapters = adapters_payload["items"]
    bots = bots_payload["items"]
    plugins = plugins_payload["items"]
    status = "warning" if errors else "ok"

    return {
        "status": status,
        "runtime": runtime,
        "stats": {
            "plugins": len(plugins),
            "loaded_plugins": sum(1 for item in plugins if item.get("loaded")),
            "commands": len(commands),
            "documented_commands": sum(1 for item in commands if item.get("documented")),
            "available_commands": sum(1 for item in commands if item.get("available", True)),
            "disabled_commands": sum(1 for item in commands if not item.get("available", True)),
            "service_commands": sum(1 for item in commands if item.get("execution_mode") == "service"),
            "service_handler_commands": sum(1 for item in commands if item.get("service_handler_registered")),
            "agent_callable_commands": sum(1 for item in commands if item.get("agent_callable")),
            "agent_executable_commands": sum(1 for item in commands if item.get("agent_executable")),
            "registry_commands": sum(1 for item in commands if item.get("metadata_source") == "command_registry"),
            "adapters": len(adapters),
            "registered_adapters": sum(1 for item in adapters if item.get("registered")),
            "bots": len(bots),
            "online_bots": sum(1 for item in bots if item.get("connected")),
        },
        "command_sources": _count_by(commands, "namespace"),
        "plugins": plugins,
        "commands": commands,
        "adapters": adapters,
        "bots": bots,
        "errors": errors,
    }


def get_runtime_info() -> dict[str, Any]:
    """读取 NoneBot 运行时初始化状态和基础配置。

    Returns:
        dict[str, Any]: 运行时状态、驱动、环境与错误列表。
    """
    config_payload = _read_nonebot_config()
    payload: dict[str, Any] = {
        "initialized": False,
        "driver": None,
        "environment": None,
        "host": None,
        "port": None,
        "config": config_payload,
        "errors": list(config_payload.get("errors", [])),
    }
    driver = get_driver()
    payload.update(
        {
            "initialized": True,
            "driver": str(getattr(driver.config, "driver", "")),
            "environment": getattr(driver.config, "environment", None),
            "host": getattr(driver.config, "host", None),
            "port": getattr(driver.config, "port", None),
        }
    )
    return payload


def list_plugins(commands: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """列出插件清单，并尽量合并运行时与源码扫描结果。

    Args:
        commands: 可选的命令扫描结果，避免重复扫描源码。

    Returns:
        dict[str, Any]: 插件列表、总数和错误信息。
    """
    load_availability_state()
    commands = commands if commands is not None else list_commands()["items"]
    config_payload = _read_nonebot_config()
    command_counts = Counter(item["plugin_module"] for item in commands if item.get("plugin_module"))
    plugin_items: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_modules: set[str] = set()

    for plugin in sorted(get_loaded_plugins(), key=lambda item: item.module_name):
        metadata = _metadata_payload(plugin.metadata)
        item = {
            "name": plugin.name,
            "module_name": plugin.module_name,
            "display_name": metadata.get("name") or plugin.name,
            "description": metadata.get("description") or "",
            "usage": metadata.get("usage") or "",
            "type": metadata.get("type"),
            "homepage": metadata.get("homepage"),
            "supported_adapters": metadata.get("supported_adapters", []),
            "loaded": True,
            "source": "runtime",
            "matcher_count": len(getattr(plugin, "matcher", set()) or []),
            "sub_plugin_count": len(getattr(plugin, "sub_plugins", set()) or []),
            "parent": getattr(plugin.parent_plugin, "module_name", None) if plugin.parent_plugin else None,
            "command_count": _command_count_for_module(command_counts, plugin.module_name),
            **_plugin_command_stats(commands, plugin.module_name),
            **_plugin_availability_payload(plugin.module_name),
        }
        seen_modules.add(plugin.module_name)
        plugin_items.append(item)

    for source_plugin in _source_plugin_summaries(commands):
        module_name = source_plugin["module_name"]
        if module_name in seen_modules:
            continue
        seen_modules.add(module_name)
        plugin_items.append(source_plugin)

    for plugin_name in config_payload.get("plugins", []):
        if any(item["module_name"] == plugin_name or item["name"] == plugin_name for item in plugin_items):
            continue
        plugin_items.append(
            {
                "name": plugin_name,
                "module_name": plugin_name,
                "display_name": plugin_name.rsplit(".", 1)[-1],
                "description": "",
                "usage": "",
                "type": "declared",
                "homepage": None,
                "supported_adapters": [],
                "loaded": False,
                "source": "pyproject",
                "matcher_count": 0,
                "sub_plugin_count": 0,
                "parent": None,
                "command_count": 0,
                **_plugin_command_stats(commands, plugin_name),
                **_plugin_availability_payload(plugin_name),
            }
        )

    plugin_items.sort(key=lambda item: (not item.get("loaded"), item.get("module_name", "")))
    return {"items": plugin_items, "total": len(plugin_items), "errors": errors}


def list_adapters() -> dict[str, Any]:
    """列出适配器声明与运行时注册状态。

    Returns:
        dict[str, Any]: 适配器列表、总数和错误信息。
    """
    config_payload = _read_nonebot_config()
    declared = config_payload.get("adapters", [])
    declared_by_module = {item["module_name"]: item for item in declared if item.get("module_name")}
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_modules: set[str] = set()

    for key, adapter in sorted(get_adapters().items(), key=lambda entry: entry[0]):
        adapter_class = adapter.__class__
        class_module = adapter_class.__module__
        module_name = _declared_adapter_module(class_module, declared_by_module) or class_module
        adapter_name = _safe_adapter_name(adapter) or key
        declared_item = declared_by_module.get(module_name, {})
        seen_modules.add(module_name)
        items.append(
            {
                "name": declared_item.get("name") or adapter_name,
                "module_name": module_name,
                "class_module": class_module,
                "runtime_key": key,
                "class_name": adapter_class.__name__,
                "registered": True,
                "source": "runtime",
                "bot_count": 0,
            }
        )

    for declared_item in declared:
        module_name = declared_item.get("module_name")
        if not module_name or module_name in seen_modules:
            continue
        items.append(
            {
                "name": declared_item.get("name") or module_name.rsplit(".", 1)[-1],
                "module_name": module_name,
                "class_module": None,
                "runtime_key": None,
                "class_name": None,
                "registered": False,
                "source": "pyproject",
                "bot_count": 0,
            }
        )

    bot_counts = Counter(bot.get("adapter_module") for bot in list_bots()["items"] if bot.get("adapter_module"))
    for item in items:
        item["bot_count"] = bot_counts.get(item.get("module_name"), 0)

    items.sort(key=lambda item: (not item.get("registered"), item.get("name", "")))
    return {"items": items, "total": len(items), "errors": errors}


def list_bots() -> dict[str, Any]:
    """列出当前在线 Bot 实例。

    Returns:
        dict[str, Any]: Bot 列表、总数和错误信息。
    """
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    for self_id, bot in sorted(get_bots().items(), key=lambda entry: entry[0]):
        adapter = getattr(bot, "adapter", None) or getattr(bot, "_adapter", None)
        adapter_class = adapter.__class__ if adapter is not None else None
        adapter_module = _adapter_module_for_class(adapter_class) if adapter_class else None
        items.append(
            {
                "self_id": getattr(bot, "self_id", self_id),
                "type": getattr(bot, "type", None),
                "adapter_name": _safe_adapter_name(adapter) if adapter is not None else None,
                "adapter_module": adapter_module,
                "connected": True,
                "status": "online",
            }
        )
    return {"items": items, "total": len(items), "errors": errors}


def list_commands() -> dict[str, Any]:
    """扫描源码中的命令声明并补全文档信息。

    Returns:
        dict[str, Any]: 命令列表、总数和扫描错误。
    """
    load_availability_state()
    commands: list[dict[str, Any]] = []
    errors: list[str] = []
    helper_index = _helper_index()
    registry_index = _registry_command_index()
    loaded_modules = _loaded_plugin_modules()

    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if _should_skip_python_file(path):
                continue
            try:
                source = path.read_text("utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, SyntaxError, UnicodeDecodeError) as error:
                errors.append(f"{relative_to_project(path)}: {error}")
                continue
            visitor = _CommandVisitor(path)
            visitor.visit(tree)
            commands.extend(
                _enrich_command(item, helper_index, registry_index, loaded_modules) for item in visitor.items
            )

    seen_commands = {item.get("command") for item in commands}
    for payload in _registry_command_payloads():
        if payload["command"] in seen_commands:
            continue
        commands.append(_registry_payload_to_command_item(payload, loaded_modules))

    commands.sort(key=lambda item: (item.get("namespace", ""), item.get("plugin_name", ""), item.get("line", 0)))
    return {"items": commands, "total": len(commands), "errors": errors}


class _CommandVisitor(ast.NodeVisitor):
    """用于扫描命令声明的 AST Visitor。"""

    def __init__(self, path: Path):
        """初始化访问器。

        Args:
            path: 当前正在扫描的 Python 文件路径。
        """
        self.path = path
        self.items: list[dict[str, Any]] = []

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        """处理赋值节点并尝试提取命令声明。"""
        self._collect(node.value, _target_names(node.targets))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        """处理带类型注解的赋值节点。"""
        if node.value is not None:
            self._collect(node.value, _target_names([node.target]))
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:  # noqa: N802
        """处理独立表达式节点。"""
        self._collect(node.value, [])
        self.generic_visit(node)

    def _collect(self, node: ast.AST, target_names: list[str]) -> None:
        """从函数调用节点中提取命令信息。

        Args:
            node: 当前 AST 节点。
            target_names: 赋值目标变量名列表。
        """
        if not isinstance(node, ast.Call):
            return
        payload = _command_payload_from_call(node)
        if payload is None:
            return
        module_name = _module_name_for_file(self.path)
        plugin_module, plugin_name, namespace = _plugin_identity_for_file(self.path)
        payload.update(
            {
                "id": f"{module_name}:{node.lineno}:{payload.get('command') or ','.join(target_names) or 'matcher'}",
                "matcher_name": target_names[0] if target_names else None,
                "file": relative_to_project(self.path),
                "line": node.lineno,
                "module_name": module_name,
                "plugin_module": plugin_module,
                "plugin_name": plugin_name,
                "namespace": namespace,
                "source": "source_scan",
            }
        )
        self.items.append(payload)


def _command_payload_from_call(node: ast.Call) -> dict[str, Any] | None:
    """从 ``on_command`` 或 ``on_alconna`` 调用中提取命令定义。"""
    func_name = _call_name(node.func).rsplit(".", 1)[-1]
    if func_name in {"on_command", "command_command"}:
        command = _literal_string(node.args[0]) if node.args else None
        matcher_type = "command"
        signature = _expression_text(node.args[0]) if node.args else ""
    elif func_name in {"on_alconna", "command_alconna"}:
        command = _alconna_command(node.args[0]) if node.args else None
        matcher_type = "alconna"
        signature = _expression_text(node.args[0]) if node.args else ""
    elif func_name == "on_agent_command":
        command = _agent_command(node.args[0]) if node.args else None
        matcher_type = "agent_command"
        signature = _expression_text(node.args[0]) if node.args else ""
    else:
        return None

    aliases = _keyword_strings(node, "aliases")
    return {
        "command": command or signature or "unknown",
        "aliases": sorted(aliases),
        "matcher_type": matcher_type,
        "priority": _keyword_value(node, "priority"),
        "block": _keyword_value(node, "block"),
        "skip_for_unmatch": _keyword_value(node, "skip_for_unmatch"),
        "signature": signature,
        "documented": False,
        "description": "",
        "ai_description": "",
        "roles": [],
        "exclude_roles": [],
        "scopes": [],
        "params": [],
        "tags": [],
        "risk_level": "low",
        "agent_callable": False,
        "execution_mode": "matcher",
        "available": True,
        "availability_reason": "",
        "service_handler_registered": False,
        "agent_executable": False,
        "tool_name": None,
        "metadata_source": "source_scan",
    }


def _enrich_command(
    item: dict[str, Any],
    helper_index: dict[str, dict[str, Any]],
    registry_index: dict[str, dict[str, Any]],
    loaded_modules: set[str],
) -> dict[str, Any]:
    """为源码扫描得到的命令补充帮助文档和加载状态。"""
    from src.platform.commands.availability import command_availability

    registry_payload = registry_index.get(item["command"])
    if registry_payload is None:
        registry_payload = next(
            (registry_index.get(alias) for alias in item.get("aliases", []) if registry_index.get(alias)),
            None,
        )
    if registry_payload:
        source_fields = {
            "id": item.get("id"),
            "matcher_name": item.get("matcher_name"),
            "file": item.get("file"),
            "line": item.get("line"),
            "module_name": item.get("module_name"),
            "plugin_module": item.get("plugin_module") or registry_payload.get("plugin_module"),
            "plugin_name": item.get("plugin_name"),
            "namespace": item.get("namespace"),
            "source": item.get("source"),
            "matcher_type": item.get("matcher_type"),
            "priority": item.get("priority"),
            "block": item.get("block"),
            "skip_for_unmatch": item.get("skip_for_unmatch"),
            "signature": item.get("signature"),
        }
        item.update(registry_payload)
        item.update({key: value for key, value in source_fields.items() if value is not None})
        item["aliases"] = sorted({*item.get("aliases", []), *registry_payload.get("aliases", [])})

    helper = helper_index.get(item["command"])
    if helper is None:
        helper = next((helper_index.get(alias) for alias in item.get("aliases", []) if helper_index.get(alias)), None)
    if helper and not registry_payload:
        item["documented"] = True
        item["description"] = helper.get("description", "")
        item["ai_description"] = helper.get("ai_description", "")
        item["roles"] = helper.get("roles", [])
        item["exclude_roles"] = helper.get("exclude_roles", [])
        item["scopes"] = helper.get("scopes", [])
        item["params"] = helper.get("params", [])
        item["tags"] = helper.get("tags", [])
        item["risk_level"] = helper.get("risk_level", "low")
        item["agent_callable"] = helper.get("agent_callable", False)
        item["execution_mode"] = helper.get("execution_mode", "matcher")
        item["tool_name"] = helper.get("tool_name")
        item["aliases"] = sorted({*item.get("aliases", []), *helper.get("aliases", [])})
        item["metadata_source"] = helper.get("metadata_source", "helper")
    elif helper:
        item["aliases"] = sorted({*item.get("aliases", []), *helper.get("aliases", [])})

    availability_decision = command_availability.check(None, item["command"])
    plugin_state = command_availability.plugin_state(item.get("plugin_module"))
    if not availability_decision.available:
        item["available"] = False
        item["availability_reason"] = availability_decision.reason
    elif not plugin_state.enabled:
        item["available"] = False
        item["availability_reason"] = plugin_state.reason or f"插件 {item.get('plugin_module') or ''} 已关闭"
    _attach_agent_execution_flags(item)
    item["runtime_loaded"] = _module_is_loaded(item["plugin_module"], loaded_modules)
    return item


def _registry_command_index() -> dict[str, dict[str, Any]]:
    """读取统一命令注册表索引。"""
    try:
        from src.platform.commands.discovery import registered_command_index
    except Exception:  # noqa: BLE001
        return {}
    return registered_command_index()


def _registry_command_payloads() -> list[dict[str, Any]]:
    """读取统一命令注册表条目。"""
    try:
        from src.platform.commands.discovery import registered_command_payloads
    except Exception:  # noqa: BLE001
        return []
    return registered_command_payloads()


def _registry_payload_to_command_item(payload: dict[str, Any], loaded_modules: set[str]) -> dict[str, Any]:
    """把注册表条目转换成管理端命令清单条目。"""
    plugin_module = payload.get("plugin_module") or ""
    plugin_name = plugin_module.rsplit(".", 1)[-1] if plugin_module else "unknown"
    namespace = (
        plugin_module.split(".")[1]
        if plugin_module.startswith("src.") and len(plugin_module.split(".")) > 1
        else "registry"
    )
    item = {
        **payload,
        "matcher_name": None,
        "file": None,
        "line": 0,
        "module_name": plugin_module,
        "plugin_module": plugin_module,
        "plugin_name": plugin_name,
        "namespace": namespace,
        "source": "command_registry",
        "matcher_type": "registered",
        "priority": None,
        "block": None,
        "skip_for_unmatch": None,
        "signature": payload["command"],
        "runtime_loaded": _module_is_loaded(plugin_module, loaded_modules),
    }
    _attach_agent_execution_flags(item)
    return item


def _attach_agent_execution_flags(item: dict[str, Any]) -> None:
    """补充管理端区分 Agent 声明可调用与真实可执行的状态。"""

    from src.platform.commands.executor import command_executor
    from src.platform.commands.registry import command_registry

    spec = command_registry.get(str(item.get("command") or ""))
    if spec is None:
        for alias in item.get("aliases", []):
            spec = command_registry.get(str(alias))
            if spec is not None:
                break

    command_name = spec.name if spec is not None else str(item.get("command") or "")
    service_handler_registered = command_executor.has_handler(command_name)
    item["service_handler_registered"] = service_handler_registered
    item["agent_executable"] = bool(
        item.get("available", True)
        and item.get("agent_callable")
        and item.get("execution_mode") == "service"
        and service_handler_registered
    )


def _plugin_availability_payload(plugin_module: str) -> dict[str, Any]:
    """读取插件级软开关状态。"""

    from src.platform.commands.availability import command_availability

    state = command_availability.plugin_state(plugin_module)
    return {
        "available": state.enabled,
        "availability_reason": state.reason,
    }


def _plugin_command_stats(commands: list[dict[str, Any]], plugin_module: str) -> dict[str, int]:
    """统计指定插件及其子模块下的命令元数据。"""

    related_commands = [
        item
        for item in commands
        if item.get("plugin_module") == plugin_module
        or str(item.get("plugin_module") or "").startswith(f"{plugin_module}.")
    ]
    return {
        "available_command_count": sum(1 for item in related_commands if item.get("available", True)),
        "disabled_command_count": sum(1 for item in related_commands if not item.get("available", True)),
        "service_command_count": sum(1 for item in related_commands if item.get("execution_mode") == "service"),
        "agent_callable_command_count": sum(1 for item in related_commands if item.get("agent_callable")),
        "high_risk_command_count": sum(1 for item in related_commands if item.get("risk_level") == "high"),
    }


def _read_nonebot_config() -> dict[str, Any]:
    """读取 ``pyproject.toml`` 中的 NoneBot 配置块。"""
    payload: dict[str, Any] = {"plugins": [], "plugin_dirs": [], "adapters": [], "errors": []}
    try:
        with PYPROJECT_PATH.open("rb") as file:
            data = tomllib.load(file)
    except OSError as error:
        payload["errors"].append(f"Unable to read pyproject.toml: {error}")
        return payload
    config = data.get("tool", {}).get("nonebot", {})
    payload["plugins"] = [str(item) for item in config.get("plugins", [])]
    payload["plugin_dirs"] = [str(item) for item in config.get("plugin_dirs", [])]
    raw_adapters = config.get("adapters", {})
    adapter_items: list[dict[str, Any]] = []
    if isinstance(raw_adapters, dict):
        for value in raw_adapters.values():
            if isinstance(value, list):
                adapter_items.extend(item for item in value if isinstance(item, dict))
    elif isinstance(raw_adapters, list):
        adapter_items = [item for item in raw_adapters if isinstance(item, dict)]
    payload["adapters"] = [
        {
            "name": str(item.get("name", "")),
            "module_name": str(item.get("module_name", "")),
        }
        for item in adapter_items
    ]
    return payload


def _metadata_payload(metadata: Any) -> dict[str, Any]:
    """把插件 metadata 对象转换成普通字典。"""
    if metadata is None:
        return {}
    return {
        "name": getattr(metadata, "name", None),
        "description": getattr(metadata, "description", None),
        "usage": getattr(metadata, "usage", None),
        "type": getattr(metadata, "type", None),
        "homepage": getattr(metadata, "homepage", None),
        "supported_adapters": sorted(
            str(getattr(item, "value", item)) for item in (getattr(metadata, "supported_adapters", None) or [])
        ),
    }


def _safe_adapter_name(adapter: Any) -> str | None:
    """安全获取适配器名称。"""
    if adapter is None:
        return None
    try:
        return adapter.get_name()
    except Exception:  # noqa: BLE001
        return adapter.__class__.__name__


def _adapter_module_for_class(adapter_class: type[Any]) -> str:
    """根据适配器类推断其声明模块名。"""
    declared = {
        item["module_name"]: item for item in _read_nonebot_config().get("adapters", []) if item.get("module_name")
    }
    return _declared_adapter_module(adapter_class.__module__, declared) or adapter_class.__module__


def _declared_adapter_module(class_module: str, declared_by_module: dict[str, dict[str, Any]]) -> str | None:
    """把运行时类模块映射回 pyproject 中声明的适配器模块。"""
    return next(
        (
            module_name
            for module_name in declared_by_module
            if class_module == module_name or class_module.startswith(f"{module_name}.")
        ),
        None,
    )


def _helper_index() -> dict[str, dict[str, Any]]:
    """构建帮助菜单命令索引，用于补全文档和参数信息。"""
    try:
        from src.platform.helper import ParamMode
        from src.platform.helper.config import helper_menu
    except Exception:  # noqa: BLE001
        return {}

    index: dict[str, dict[str, Any]] = {}
    for helper in getattr(helper_menu, "helpers", []):
        payload = {
            "command": helper.command,
            "description": helper.description,
            "ai_description": helper.ai_description or "",
            "aliases": sorted(map(str, helper.aliases)),
            "roles": sorted(map(str, helper.roles)),
            "exclude_roles": sorted(map(str, helper.exclude_roles)),
            "scopes": sorted(map(str, helper.display_scopes)),
            "params": [
                {
                    "name": param.name,
                    "description": param.description or "",
                    "mode": str(param.mode) if param.mode else None,
                    "value_type": "string",
                    "multiple": param.mode in {ParamMode.ONE_OR_MORE, ParamMode.ZERO_OR_MORE},
                    "source_name": None,
                    "required": param.mode not in {ParamMode.OPTIONAL, ParamMode.ZERO_OR_MORE},
                }
                for param in helper.params
            ],
            "tags": sorted(map(str, helper.tags)),
            "risk_level": "low",
            "agent_callable": False,
            "execution_mode": "matcher",
            "tool_name": None,
            "metadata_source": "helper",
        }
        for command in helper.commands:
            index[str(command)] = payload
    return index


def _loaded_plugin_modules() -> set[str]:
    """获取当前已加载插件模块集合。"""
    return {plugin.module_name for plugin in get_loaded_plugins()}


def _module_is_loaded(plugin_module: str, loaded_modules: set[str]) -> bool:
    """判断插件模块是否已在运行时加载。"""
    return any(plugin_module == module or module.startswith(f"{plugin_module}.") for module in loaded_modules)


def _source_plugin_summaries(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """根据命令扫描结果推断源码插件摘要。"""
    grouped: dict[str, dict[str, Any]] = {}
    for command in commands:
        plugin_module = command["plugin_module"]
        grouped.setdefault(
            plugin_module,
            {
                "name": command["plugin_name"],
                "module_name": plugin_module,
                "display_name": command["plugin_name"],
                "description": "",
                "usage": "",
                "type": command["namespace"],
                "homepage": None,
                "supported_adapters": [],
                "loaded": command.get("runtime_loaded", False),
                "source": "source_scan",
                "matcher_count": 0,
                "sub_plugin_count": 0,
                "parent": None,
                "command_count": 0,
                "available": True,
                "availability_reason": "",
                "available_command_count": 0,
                "disabled_command_count": 0,
                "service_command_count": 0,
                "agent_callable_command_count": 0,
                "high_risk_command_count": 0,
            },
        )
        grouped[plugin_module]["command_count"] += 1
        grouped[plugin_module]["available_command_count"] += 1 if command.get("available", True) else 0
        grouped[plugin_module]["disabled_command_count"] += 0 if command.get("available", True) else 1
        grouped[plugin_module]["service_command_count"] += 1 if command.get("execution_mode") == "service" else 0
        grouped[plugin_module]["agent_callable_command_count"] += 1 if command.get("agent_callable") else 0
        grouped[plugin_module]["high_risk_command_count"] += 1 if command.get("risk_level") == "high" else 0
        if not command.get("available", True):
            grouped[plugin_module]["available"] = False
            grouped[plugin_module]["availability_reason"] = command.get("availability_reason", "")
    return sorted(grouped.values(), key=lambda item: item["module_name"])


def _command_count_for_module(command_counts: Counter[str], module_name: str) -> int:
    """统计插件模块及其子模块命令数量。"""
    return sum(
        count
        for plugin_module, count in command_counts.items()
        if plugin_module == module_name or plugin_module.startswith(f"{module_name}.")
    )


def _should_skip_python_file(path: Path) -> bool:
    """判断源码扫描时是否应跳过当前文件。"""
    return "__pycache__" in path.parts or path.name.startswith(".")


def _target_names(targets: Iterable[ast.AST]) -> list[str]:
    """提取赋值节点中的变量名列表。"""
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Tuple):
            names.extend(_target_names(target.elts))
    return names


def _call_name(node: ast.AST) -> str:
    """把函数调用 AST 节点还原成点路径名称。"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _literal_string(node: ast.AST) -> str | None:
    """尝试从 AST 节点中提取字符串字面量。"""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _alconna_command(node: ast.AST) -> str | None:
    """提取 ``Alconna`` 命令名称。"""
    if isinstance(node, ast.Call) and _call_name(node.func).rsplit(".", 1)[-1] == "Alconna" and node.args:
        return _literal_string(node.args[0])
    return _literal_string(node)


def _agent_command(node: ast.AST) -> str | None:
    """提取 ``on_agent_command`` 的命令名称。"""

    return _alconna_command(node) or _literal_string(node)


def _keyword_strings(node: ast.Call, keyword_name: str) -> set[str]:
    """提取调用关键字参数中的字符串集合。"""
    keyword = _find_keyword(node, keyword_name)
    if keyword is None:
        return set()
    return _string_collection(keyword.value)


def _keyword_value(node: ast.Call, keyword_name: str) -> Any:
    """提取调用关键字参数的原始值或表达式文本。"""
    keyword = _find_keyword(node, keyword_name)
    if keyword is None:
        return None
    value = keyword.value
    if isinstance(value, ast.Constant):
        return value.value
    return _expression_text(value)


def _find_keyword(node: ast.Call, keyword_name: str) -> ast.keyword | None:
    """按名称查找调用中的关键字参数。"""
    return next((keyword for keyword in node.keywords if keyword.arg == keyword_name), None)


def _string_collection(node: ast.AST) -> set[str]:
    """从 AST 节点中提取字符串集合。"""
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return {item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)}
    literal = _literal_string(node)
    return {literal} if literal else set()


def _expression_text(node: ast.AST) -> str:
    """把 AST 节点尽量还原成源码文本。"""
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return ""


def _module_name_for_file(path: Path) -> str:
    """根据文件路径推断 Python 模块名。"""
    relative = path.resolve().relative_to(project_root.resolve()).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _plugin_identity_for_file(path: Path) -> tuple[str, str, str]:
    """根据源码文件路径推断插件模块、插件名和命名空间。"""
    relative = path.resolve().relative_to(project_root.resolve())
    parts = relative.parts
    if len(parts) >= 3 and parts[0] == "src":
        namespace = parts[1]
        plugin_name = parts[2]
        return ".".join(("src", namespace, plugin_name)), plugin_name, namespace
    module = _module_name_for_file(path)
    return module, module.rsplit(".", 1)[-1], "unknown"


def _count_by(items: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    """按指定字段统计条目数量。"""
    return dict(sorted(Counter(str(item.get(key) or "unknown") for item in items).items()))
