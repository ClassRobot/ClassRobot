from __future__ import annotations

import os
import sys
import subprocess


def find_python_with_pyright() -> str:
    """寻找带有 pyright 模块的 Python 解释器。"""
    # 1. 尝试当前解释器
    try:
        subprocess.run([sys.executable, "-c", "import pyright"], check=True, capture_output=True)
        return sys.executable
    except Exception:
        pass

    # 2. 尝试常见的虚拟环境解释器路径
    alternatives = [
        r"D:\Software\anaconda3\envs\classbot\python.exe",
        os.path.join(".venv", "Scripts", "python.exe"),
        os.path.join(".venv", "bin", "python"),
        os.path.join("venv", "Scripts", "python.exe"),
        os.path.join("venv", "bin", "python"),
    ]
    for alt in alternatives:
        if os.path.exists(alt):
            try:
                subprocess.run([alt, "-c", "import pyright"], check=True, capture_output=True)
                return alt
            except Exception:
                pass

    # 3. 兜底返回当前解释器
    return sys.executable


def main() -> int:
    """使用当前解释器执行 Pyright，确保本地环境和 CI 的解析结果一致。"""

    pyright_args = sys.argv[1:]
    if pyright_args and pyright_args[0] == "--":
        pyright_args = pyright_args[1:]

    python_exe = find_python_with_pyright()
    command = [python_exe, "-m", "pyright", "--pythonpath", python_exe, *pyright_args]
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
