from __future__ import annotations

import subprocess
import sys


def main() -> int:
    """使用当前解释器执行 Pyright，确保本地环境和 CI 的解析结果一致。"""

    pyright_args = sys.argv[1:]
    if pyright_args and pyright_args[0] == "--":
        pyright_args = pyright_args[1:]
    command = [sys.executable, "-m", "pyright", "--pythonpath", sys.executable, *pyright_args]
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
