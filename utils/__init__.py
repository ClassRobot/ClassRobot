from typing import Any, TypeVar, Callable

T = TypeVar("T")


def tip(msg: T) -> Callable[..., T]:
    return lambda *_: msg
