from functools import wraps, partial
from typing_extensions import ParamSpec
from typing import Any, TypeVar, Callable, Coroutine

import anyio

P = ParamSpec("P")
R = TypeVar("R")


def run_sync(func: Callable[P, R]) -> Callable[P, Coroutine[Any, Any, R]]:  # type: ignore
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore
        return await anyio.to_thread.run_sync(partial(func, *args, **kwargs))
    return wrapper


def run_async(func: Callable[P, Coroutine[Any, Any, R]]) -> Callable[P, R]:  # type: ignore
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore
        return anyio.from_thread.run(partial(func, *args, **kwargs))
    return wrapper
