import itertools
from typing import TypeVar, Callable

from strenum import StrEnum

from .tools import check_punctuation

T = TypeVar("T")


ValidateName = lambda name: check_punctuation(name)  # noqa: E731


class Emoji(StrEnum):
    win = "🎉"
    "庆祝"
    error = "❌"
    "错误"
    success = "✅"
    "成功"
    warning = "⚠️"
    "警告"
    info = "ℹ️"
    "信息"
    question = "❓"
    "问题"
    loading = "⏳"
    "加载"
    bulb = "💡"
    "灯泡"

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
