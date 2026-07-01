"""Core exceptions raised by the Redis client"""

import builtins


class RedisError(Exception):
    """表示rediserror异常。"""

    pass


class ConnectionError(RedisError):
    """表示connectionerror异常。"""

    pass


class TimeoutError(builtins.TimeoutError, RedisError):
    """表示timeouterror异常。"""

    pass


class AuthenticationError(ConnectionError):
    """表示authenticationerror异常。"""

    pass


class BusyLoadingError(ConnectionError):
    """表示busyloadingerror异常。"""

    pass


class InvalidResponse(RedisError):
    """表示invalidresponse异常。"""

    pass


class ResponseError(RedisError):
    """表示responseerror异常。"""

    pass


class DataError(RedisError):
    """表示dataerror异常。"""

    pass


class PubSubError(RedisError):
    """表示pubsuberror异常。"""

    pass


class WatchError(RedisError):
    """表示watcherror异常。"""

    pass


class NoScriptError(ResponseError):
    """表示noscripterror异常。"""

    pass


class ExecAbortError(ResponseError):
    """表示execaborterror异常。"""

    pass


class ReadOnlyError(ResponseError):
    """表示读取onlyerror异常。"""

    pass


class NoPermissionError(ResponseError):
    """表示no权限error异常。"""

    pass


class ModuleError(ResponseError):
    """表示moduleerror异常。"""

    pass


class LockError(RedisError, ValueError):
    """Errors acquiring or releasing a lock"""

    # NOTE: For backwards compatibility, this class derives from ValueError.
    # This was originally chosen to behave like threading.Lock.
    pass


class LockNotOwnedError(LockError):
    """Error trying to extend or release a lock that is (no longer) owned"""

    pass


class ChildDeadlockedError(Exception):
    """Error indicating that a child process is deadlocked after a fork()"""

    pass


class AuthenticationWrongNumberOfArgsError(ResponseError):
    """
    An error to indicate that the wrong number of args
    were sent to the AUTH command
    """

    pass
