from functools import wraps, partial
from typing_extensions import ParamSpec
from typing import Any, TypeVar, Callable, Coroutine

import anyio.to_thread
import anyio.from_thread

R = TypeVar("R")
P = ParamSpec("P")


def run_sync(func: Callable[P, R]) -> Callable[P, Coroutine[Any, Any, R]]:
    """将同步函数包装为异步调用。"""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        """包装原始函数调用。"""
        return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))

    return wrapper


def run_async(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, R]:
    """将异步函数包装为同步调用。"""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        """包装原始函数调用。"""
        return anyio.from_thread.run(partial(func, *args, **kwargs))

    return wrapper
