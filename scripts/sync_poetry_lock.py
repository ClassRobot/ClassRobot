"""在提交前同步 Poetry 锁文件。"""

from __future__ import annotations

from pathlib import Path
from sys import argv, exit
from subprocess import CompletedProcess, run

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_FILE = REPO_ROOT / "poetry.lock"


def run_command(*args: str) -> CompletedProcess[str]:
    """在仓库根目录执行命令，并保持失败时立即中断。"""

    return run(
        args,
        cwd=REPO_ROOT,
        check=True,
        text=True,
    )


def sync_poetry_lock() -> None:
    """同步 Poetry 锁文件。

    只要 `pyproject.toml` 参与本次提交，就在 commit 阶段自动：

    1. 执行 `poetry lock --no-interaction`
    2. 把 `poetry.lock` 加入当前暂存区
    """

    run_command("poetry", "lock", "--no-interaction")
    run_command("git", "add", str(LOCK_FILE))


def main() -> int:
    """在 pre-commit 环境中执行同步逻辑。"""

    changed_files = {Path(path).as_posix() for path in argv[1:]}
    if "pyproject.toml" not in changed_files:
        return 0
    sync_poetry_lock()
    return 0


if __name__ == "__main__":
    exit(main())
