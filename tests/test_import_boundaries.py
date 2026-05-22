from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LEGACY_IMPORT_PREFIXES = ("core", "utils", "src.features")
REMOVED_ROOTS = (
    PROJECT_ROOT / "core",
    PROJECT_ROOT / "utils",
    PROJECT_ROOT / "src" / "features",
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
            if any(module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in LEGACY_IMPORT_PREFIXES):
                relative = path.relative_to(PROJECT_ROOT).as_posix()
                violations.append(f"{relative}: {module_name}")

    assert not violations, "removed namespace imports found:\n" + "\n".join(violations)
