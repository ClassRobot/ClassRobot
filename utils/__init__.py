import itertools
from typing import TypeVar, Callable

from strenum import StrEnum
from nonebot_plugin_alconna import File, Other

from .tools import check_punctuation

T = TypeVar("T")


ValidateName = lambda name: (None if name.isdigit() or check_punctuation(name) else name)  # noqa: E731


class Emoji(StrEnum):
    """定义项目中使用的表情符号枚举值。"""

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
        """调用实例并返回结果。

        参数:
            sep (str): sep。
            msg (*str): msg。

        返回:
            str: 返回字符串结果。
        """
        return self + sep + sep.join(msg)


def tip(msg: T) -> Callable[..., T]:
    """返回固定提示内容。"""
    return lambda *_: msg


def file_or_other_file(file: File | Other) -> File:
    """将文件消息转换为统一的文件对象。"""
    if isinstance(file, File):
        return file
    elif isinstance(file, Other):
        return File(
            name=file.origin.data["file_name"],
            url=file.origin.data["url"],
            id=file.origin.data["file_id"],
        )


FileOrOtherFile = lambda file: file_or_other_file(file)  # noqa: E731


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
