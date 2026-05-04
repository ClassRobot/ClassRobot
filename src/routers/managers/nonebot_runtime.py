from __future__ import annotations

import ast
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from utils.config import project_root

from .service import relative_to_project

PYPROJECT_PATH = project_root / "pyproject.toml"
SOURCE_ROOTS = (
    project_root / "src" / "managers",
    project_root / "src" / "plugins",
    project_root / "src" / "others",
)


def get_nonebot_overview() -> dict[str, Any]:
    """Return a read-only inventory of the current NoneBot runtime."""

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
    try:
        from nonebot import get_driver

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
    except Exception as error:  # noqa: BLE001 - this endpoint must degrade safely during startup/tests.
        payload["errors"].append(f"NoneBot runtime is not initialized: {error}")
    return payload


def list_plugins(commands: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    commands = commands if commands is not None else list_commands()["items"]
    config_payload = _read_nonebot_config()
    command_counts = Counter(item["plugin_module"] for item in commands if item.get("plugin_module"))
    plugin_items: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_modules: set[str] = set()

    try:
        from nonebot import get_loaded_plugins

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
            }
            seen_modules.add(plugin.module_name)
            plugin_items.append(item)
    except Exception as error:  # noqa: BLE001
        errors.append(f"Unable to read loaded plugins: {error}")

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
            }
        )

    plugin_items.sort(key=lambda item: (not item.get("loaded"), item.get("module_name", "")))
    return {"items": plugin_items, "total": len(plugin_items), "errors": errors}


def list_adapters() -> dict[str, Any]:
    config_payload = _read_nonebot_config()
    declared = config_payload.get("adapters", [])
    declared_by_module = {item["module_name"]: item for item in declared if item.get("module_name")}
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_modules: set[str] = set()

    try:
        from nonebot import get_adapters

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
    except Exception as error:  # noqa: BLE001
        errors.append(f"Unable to read registered adapters: {error}")

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
    items: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        from nonebot import get_bots

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
    except Exception as error:  # noqa: BLE001
        errors.append(f"Unable to read connected bots: {error}")
    return {"items": items, "total": len(items), "errors": errors}


def list_commands() -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    errors: list[str] = []
    helper_index = _helper_index()
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
            commands.extend(_enrich_command(item, helper_index, loaded_modules) for item in visitor.items)

    commands.sort(key=lambda item: (item.get("namespace", ""), item.get("plugin_name", ""), item.get("line", 0)))
    return {"items": commands, "total": len(commands), "errors": errors}


class _CommandVisitor(ast.NodeVisitor):
    def __init__(self, path: Path):
        self.path = path
        self.items: list[dict[str, Any]] = []

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        self._collect(node.value, _target_names(node.targets))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if node.value is not None:
            self._collect(node.value, _target_names([node.target]))
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:  # noqa: N802
        self._collect(node.value, [])
        self.generic_visit(node)

    def _collect(self, node: ast.AST, target_names: list[str]) -> None:
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
    func_name = _call_name(node.func).rsplit(".", 1)[-1]
    if func_name == "on_command":
        command = _literal_string(node.args[0]) if node.args else None
        matcher_type = "command"
        signature = _expression_text(node.args[0]) if node.args else ""
    elif func_name == "on_alconna":
        command = _alconna_command(node.args[0]) if node.args else None
        matcher_type = "alconna"
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
        "roles": [],
        "scopes": [],
        "params": [],
    }


def _enrich_command(
    item: dict[str, Any],
    helper_index: dict[str, dict[str, Any]],
    loaded_modules: set[str],
) -> dict[str, Any]:
    helper = helper_index.get(item["command"])
    if helper is None:
        helper = next((helper_index.get(alias) for alias in item.get("aliases", []) if helper_index.get(alias)), None)
    if helper:
        item["documented"] = True
        item["description"] = helper.get("description", "")
        item["roles"] = helper.get("roles", [])
        item["scopes"] = helper.get("scopes", [])
        item["params"] = helper.get("params", [])
        item["aliases"] = sorted({*item.get("aliases", []), *helper.get("aliases", [])})
    item["runtime_loaded"] = _module_is_loaded(item["plugin_module"], loaded_modules)
    return item


def _read_nonebot_config() -> dict[str, Any]:
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
    payload["adapters"] = [
        {
            "name": str(item.get("name", "")),
            "module_name": str(item.get("module_name", "")),
        }
        for item in config.get("adapters", [])
        if isinstance(item, dict)
    ]
    return payload


def _metadata_payload(metadata: Any) -> dict[str, Any]:
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
    if adapter is None:
        return None
    try:
        return adapter.get_name()
    except Exception:  # noqa: BLE001
        return adapter.__class__.__name__


def _adapter_module_for_class(adapter_class: type[Any]) -> str:
    declared = {
        item["module_name"]: item for item in _read_nonebot_config().get("adapters", []) if item.get("module_name")
    }
    return _declared_adapter_module(adapter_class.__module__, declared) or adapter_class.__module__


def _declared_adapter_module(class_module: str, declared_by_module: dict[str, dict[str, Any]]) -> str | None:
    return next(
        (
            module_name
            for module_name in declared_by_module
            if class_module == module_name or class_module.startswith(f"{module_name}.")
        ),
        None,
    )


def _helper_index() -> dict[str, dict[str, Any]]:
    try:
        from utils.helper.config import helper_menu
    except Exception:  # noqa: BLE001
        return {}

    index: dict[str, dict[str, Any]] = {}
    for helper in getattr(helper_menu, "helpers", []):
        payload = {
            "command": helper.command,
            "description": helper.description,
            "aliases": sorted(map(str, helper.aliases)),
            "roles": sorted(map(str, helper.roles)),
            "scopes": sorted(map(str, helper.display_scopes)),
            "params": [
                {
                    "name": param.name,
                    "description": param.description,
                    "mode": str(param.mode) if param.mode else None,
                }
                for param in helper.params
            ],
        }
        for command in helper.commands:
            index[str(command)] = payload
    return index


def _loaded_plugin_modules() -> set[str]:
    try:
        from nonebot import get_loaded_plugins

        return {plugin.module_name for plugin in get_loaded_plugins()}
    except Exception:  # noqa: BLE001
        return set()


def _module_is_loaded(plugin_module: str, loaded_modules: set[str]) -> bool:
    return any(plugin_module == module or module.startswith(f"{plugin_module}.") for module in loaded_modules)


def _source_plugin_summaries(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            },
        )
        grouped[plugin_module]["command_count"] += 1
    return sorted(grouped.values(), key=lambda item: item["module_name"])


def _command_count_for_module(command_counts: Counter[str], module_name: str) -> int:
    return sum(
        count
        for plugin_module, count in command_counts.items()
        if plugin_module == module_name or plugin_module.startswith(f"{module_name}.")
    )


def _should_skip_python_file(path: Path) -> bool:
    return "__pycache__" in path.parts or path.name.startswith(".")


def _target_names(targets: Iterable[ast.AST]) -> list[str]:
    names: list[str] = []
    for target in targets:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Tuple):
            names.extend(_target_names(target.elts))
    return names


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _literal_string(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _alconna_command(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and _call_name(node.func).rsplit(".", 1)[-1] == "Alconna" and node.args:
        return _literal_string(node.args[0])
    return _literal_string(node)


def _keyword_strings(node: ast.Call, keyword_name: str) -> set[str]:
    keyword = _find_keyword(node, keyword_name)
    if keyword is None:
        return set()
    return _string_collection(keyword.value)


def _keyword_value(node: ast.Call, keyword_name: str) -> Any:
    keyword = _find_keyword(node, keyword_name)
    if keyword is None:
        return None
    value = keyword.value
    if isinstance(value, ast.Constant):
        return value.value
    return _expression_text(value)


def _find_keyword(node: ast.Call, keyword_name: str) -> ast.keyword | None:
    return next((keyword for keyword in node.keywords if keyword.arg == keyword_name), None)


def _string_collection(node: ast.AST) -> set[str]:
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return {item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)}
    literal = _literal_string(node)
    return {literal} if literal else set()


def _expression_text(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001
        return ""


def _module_name_for_file(path: Path) -> str:
    relative = path.resolve().relative_to(project_root.resolve()).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _plugin_identity_for_file(path: Path) -> tuple[str, str, str]:
    relative = path.resolve().relative_to(project_root.resolve())
    parts = relative.parts
    if len(parts) >= 3 and parts[0] == "src":
        namespace = parts[1]
        plugin_name = parts[2]
        return ".".join(("src", namespace, plugin_name)), plugin_name, namespace
    module = _module_name_for_file(path)
    return module, module.rsplit(".", 1)[-1], "unknown"


def _count_by(items: Iterable[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(item.get(key) or "unknown") for item in items).items()))
