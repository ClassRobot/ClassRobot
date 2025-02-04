import itertools
from typing import TypeVar, Callable

from strenum import StrEnum

T = TypeVar("T")
ValidateName = lambda name: None if name.strip().isdigit() else name


class Emoji(StrEnum):
    win = "🎉"
    error = "❌"
    success = "✅"
    warning = "⚠️"
    info = "ℹ️"
    question = "❓"
    loading = "⏳"

    def __call__(self, *msg: str, sep: str = "") -> str:
        return self + sep + sep.join(msg)


def tip(msg: T) -> Callable[..., T]:
    return lambda *_: msg


def alias_product(*args: list[str]):
    """别名组成
    ```python
    alias(["创建", "添加"], ["任务", "作业])
    ```
    ```
    {"创建任务", "添加任务", "创建作业", "添加作业" }
    ```
    """
    return {"".join(i) for i in itertools.product(*args)}
