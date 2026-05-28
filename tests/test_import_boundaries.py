from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_IMPORT_PREFIXES = ("core", "utils", "src.features")
REMOVED_INTERNAL_PREFIXES = (
    "src.shared.schemas",
    "src.shared.template",
    "src.shared.tools.cos",
    "src.shared.encrypt",
    "src.models.depends",
    "src.models.params",
    "src.plugins.library.message_history.resolvers",
)
REMOVED_ROOTS = (
    PROJECT_ROOT / "core",
    PROJECT_ROOT / "utils",
    PROJECT_ROOT / "src" / "features",
    PROJECT_ROOT / "src" / "shared" / "schemas",
    PROJECT_ROOT / "src" / "shared" / "template",
    PROJECT_ROOT / "src" / "shared" / "tools" / "cos",
    PROJECT_ROOT / "src" / "shared" / "encrypt",
    PROJECT_ROOT / "src" / "models" / "params",
)


def _iter_python_files() -> list[Path]:
    """返回需要检查导入边界的 Python 源文件。"""

    ignored_parts = {"__pycache__"}
    roots = (PROJECT_ROOT / "src", PROJECT_ROOT / "tests")
    files: list[Path] = []
    for root in roots:
        for path in root.rglob("*.py"):
            if ignored_parts.intersection(path.parts):
                continue
            files.append(path)
    return files


def _iter_imported_modules(path: Path) -> list[str]:
    """解析单个文件中出现的绝对导入模块。"""

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
    return modules


def test_removed_code_roots_do_not_exist():
    """旧代码根已经移除，避免新代码继续依赖兼容入口。"""

    for root in REMOVED_ROOTS:
        assert not root.exists(), f"legacy code root should be removed: {root}"


def test_python_code_does_not_import_removed_namespaces():
    """业务代码和测试不能再导入旧命名空间。"""

    violations: list[str] = []
    for path in _iter_python_files():
        for module_name in _iter_imported_modules(path):
            removed_prefixes = LEGACY_IMPORT_PREFIXES + REMOVED_INTERNAL_PREFIXES
            if any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in removed_prefixes):
                relative = path.relative_to(PROJECT_ROOT).as_posix()
                violations.append(f"{relative}: {module_name}")

    assert not violations, "removed namespace imports found:\n" + "\n".join(violations)


def test_shared_layer_has_no_platform_or_core_imports():
    """shared 只能提供纯工具或 vendored 包，不能反向依赖平台、核心或插件层。"""

    forbidden_prefixes = (
        "nonebot",
        "nonebot_plugin",
        "src.core",
        "src.platform",
        "src.plugins",
    )
    violations: list[str] = []
    shared_root = PROJECT_ROOT / "src" / "shared"
    for path in shared_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for module_name in _iter_imported_modules(path):
            if any(
                module_name == prefix or module_name.startswith(f"{prefix}.") or module_name.startswith(f"{prefix}_")
                for prefix in forbidden_prefixes
            ):
                relative = path.relative_to(PROJECT_ROOT).as_posix()
                violations.append(f"{relative}: {module_name}")

    assert not violations, "shared layer imports forbidden modules:\n" + "\n".join(violations)


def test_core_layer_does_not_import_plugins():
    """core 可以被插件调用，但不能反向依赖具体插件实现。"""

    violations: list[str] = []
    core_root = PROJECT_ROOT / "src" / "core"
    for path in core_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for module_name in _iter_imported_modules(path):
            if module_name == "src.plugins" or module_name.startswith("src.plugins."):
                relative = path.relative_to(PROJECT_ROOT).as_posix()
                violations.append(f"{relative}: {module_name}")

    assert not violations, "core layer imports plugin modules:\n" + "\n".join(violations)


def test_library_message_history_has_no_matcher_or_command_entrypoints():
    """message_history library 只提供复用能力，不注册 matcher 或命令入口。"""

    forbidden_names = {
        "on_message",
        "on_agent_command",
        "on_alconna",
        "on_command",
        "command_executor",
        "register_command_input_recorder",
    }
    library_root = PROJECT_ROOT / "src" / "plugins" / "library" / "message_history"
    assert not (library_root / "commands.py").exists()

    violations: list[str] = []
    for path in library_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_names or alias.name.rsplit(".", 1)[-1] in forbidden_names:
                        violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    if alias.name in forbidden_names:
                        violations.append(
                            f"{path.relative_to(PROJECT_ROOT).as_posix()}: from {node.module} import {alias.name}"
                        )
            elif isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name in forbidden_names or name == "handle":
                    violations.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}: call {name}")

    assert not violations, "message_history library contains matcher or command entrypoints:\n" + "\n".join(violations)
