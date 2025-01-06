from typing import TypeVar, Callable

T = TypeVar("T")


def tip(msg: T) -> Callable[[], T]:
    return lambda: msg
