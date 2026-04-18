from .utils import from_url
from .client import Redis, StrictRedis
from .connection import Connection, SSLConnection, ConnectionPool, BlockingConnectionPool, UnixDomainSocketConnection
from .exceptions import (
    DataError,
    RedisError,
    WatchError,
    PubSubError,
    TimeoutError,
    ReadOnlyError,
    ResponseError,
    ConnectionError,
    InvalidResponse,
    BusyLoadingError,
    AuthenticationError,
    ChildDeadlockedError,
    AuthenticationWrongNumberOfArgsError,
)


def int_or_str(value):
    try:
        return int(value)
    except ValueError:
        return value


__version__ = "2.0.1"
VERSION = tuple(map(int_or_str, __version__.split(".")))

__all__ = [
    "AuthenticationError",
    "AuthenticationWrongNumberOfArgsError",
    "BlockingConnectionPool",
    "BusyLoadingError",
    "ChildDeadlockedError",
    "Connection",
    "ConnectionError",
    "ConnectionPool",
    "DataError",
    "from_url",
    "InvalidResponse",
    "PubSubError",
    "ReadOnlyError",
    "Redis",
    "RedisError",
    "ResponseError",
    "SSLConnection",
    "StrictRedis",
    "TimeoutError",
    "UnixDomainSocketConnection",
    "WatchError",
]
