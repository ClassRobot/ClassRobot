"""在提交前同步 Poetry 锁文件与 requirements 导出文件。"""

from __future__ import annotations

from os import environ
from pathlib import Path
from importlib.util import find_spec
from sys import argv, exit, executable
from subprocess import CompletedProcess, CalledProcessError, run

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_FILE = REPO_ROOT / "poetry.lock"
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"
BOOTSTRAP_ENV = "CLASSROBOT_POETRY_SYNC_BOOTSTRAP"


def run_command(*args: str) -> CompletedProcess[str]:
    """在仓库根目录执行命令，并保持失败时立即中断。"""

    return run(
        args,
        cwd=REPO_ROOT,
        check=True,
        text=True,
    )


def poetry_command_prefix() -> tuple[str, ...]:
    """返回当前环境可用的 Poetry 调用前缀。

    pre-commit 的 `language: python` hook 会把 Poetry 安装到独立环境里，
    此时优先使用当前解释器的 `python -m poetry`，避免依赖开发机全局
    Poetry 插件状态。普通手动调用脚本时，再回退到外部 `poetry` 命令。
    """

    if find_spec("poetry") is not None:
        return (executable, "-m", "poetry")
    return ("poetry",)


def run_poetry_command(*args: str) -> CompletedProcess[str]:
    """执行 Poetry 子命令，并在导出能力缺失时给出清晰报错。"""

    if args and args[0] == "export" and find_spec("poetry") is None and maybe_bootstrap_with_pre_commit():
        return CompletedProcess(args=args, returncode=0)
    try:
        return run_command(*poetry_command_prefix(), *args)
    except CalledProcessError as error:
        if args and args[0] == "export" and maybe_bootstrap_with_pre_commit():
            return CompletedProcess(args=args, returncode=0)
        if args and args[0] == "export":
            raise RuntimeError(
                "当前 Poetry 环境没有可用的 export 能力。"
                "请通过 pre-commit 的 poetry-sync hook 运行，"
                "或先为当前 Poetry 安装 poetry-plugin-export。"
            ) from error
        raise


def maybe_bootstrap_with_pre_commit() -> bool:
    """在手动运行脚本时回退到 pre-commit 的隔离环境。

    当前开发机上的 Poetry 可能没有安装 `poetry-plugin-export`。遇到这种
    情况时，如果本次不是由 pre-commit hook 本身触发，就转而调用
    `pre-commit run poetry-sync --files ...`，复用 hook 自带的 Poetry 2 +
    export 插件环境。
    """

    if environ.get(BOOTSTRAP_ENV) == "1":
        return False
    changed_files = [path for path in argv[1:] if path]
    if not changed_files:
        return False

    child_env = dict(environ)
    child_env[BOOTSTRAP_ENV] = "1"
    run(
        ("poetry", "run", "pre-commit", "run", "poetry-sync", "--files", *changed_files),
        cwd=REPO_ROOT,
        check=True,
        text=True,
        env=child_env,
    )
    return True


def lock_dependencies() -> None:
    """根据 `pyproject.toml` 重新生成锁文件。"""

    run_poetry_command("lock", "--no-interaction")


def export_requirements() -> None:
    """根据锁文件导出受控的 `requirements.txt`。"""

    run_poetry_command("export", "-f", "requirements.txt", "--output", "requirements.txt")


def stage_dependency_outputs() -> None:
    """把依赖同步产物加入当前暂存区。"""

    run_command("git", "add", str(LOCK_FILE), str(REQUIREMENTS_FILE))


def main() -> int:
    """在 pre-commit 环境中执行依赖同步逻辑。

    行为约定：

    - `pyproject.toml` 改动时：执行 lock + export
    - `poetry.lock` 改动时：只执行 export
    - 其他文件改动：不触发依赖同步
    """

    changed_files = {Path(path).as_posix() for path in argv[1:]}
    if "pyproject.toml" in changed_files:
        lock_dependencies()
        export_requirements()
        stage_dependency_outputs()
        return 0
    if "poetry.lock" in changed_files:
        export_requirements()
        stage_dependency_outputs()
        return 0
    if not changed_files:
        return 0
    return 0


if __name__ == "__main__":
    exit(main())
