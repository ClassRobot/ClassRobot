import uuid
import asyncio
import threading
from types import SimpleNamespace
from typing import TYPE_CHECKING, Union, NoReturn, Optional, Awaitable

from .exceptions import LockError, LockNotOwnedError

if TYPE_CHECKING:
    from . import Redis


class Lock:
    """
    A shared, distributed Lock. Using Redis for locking allows the Lock
    to be shared across processes and/or machines.

    It's left to the user to resolve deadlock issues and make sure
    multiple clients play nicely together.
    """

    lua_release = None
    lua_extend = None
    lua_reacquire = None

    # KEYS[1] - lock name
    # ARGV[1] - token
    # return 1 if the lock was released, otherwise 0
    LUA_RELEASE_SCRIPT = """
        local token = redis.call('get', KEYS[1])
        if not token or token ~= ARGV[1] then
            return 0
        end
        redis.call('del', KEYS[1])
        return 1
    """

    # KEYS[1] - lock name
    # ARGV[1] - token
    # ARGV[2] - additional milliseconds
    # ARGV[3] - "0" if the additional time should be added to the lock's
    #           existing ttl or "1" if the existing ttl should be replaced
    # return 1 if the locks time was extended, otherwise 0
    LUA_EXTEND_SCRIPT = """
        local token = redis.call('get', KEYS[1])
        if not token or token ~= ARGV[1] then
            return 0
        end
        local expiration = redis.call('pttl', KEYS[1])
        if not expiration then
            expiration = 0
        end
        if expiration < 0 then
            return 0
        end

        local newttl = ARGV[2]
        if ARGV[3] == "0" then
            newttl = ARGV[2] + expiration
        end
        redis.call('pexpire', KEYS[1], newttl)
        return 1
    """

    # KEYS[1] - lock name
    # ARGV[1] - token
    # ARGV[2] - milliseconds
    # return 1 if the locks time was reacquired, otherwise 0
    LUA_REACQUIRE_SCRIPT = """
        local token = redis.call('get', KEYS[1])
        if not token or token ~= ARGV[1] then
            return 0
        end
        redis.call('pexpire', KEYS[1], ARGV[2])
        return 1
    """

    def __init__(
        self,
        redis: "Redis",
        name: Union[str, bytes, memoryview],
        timeout: Optional[float] = None,
        sleep: float = 0.1,
        blocking: bool = True,
        blocking_timeout: Optional[float] = None,
        thread_local: bool = True,
    ):
        """Create a new Lock instance named ``name`` using the Redis client

        参数:
            redis ('Redis'): redis。
            name (Union[str, bytes, memoryview]): 名称。
            timeout (Optional[float]): timeout。
            sleep (float): sleep。
            blocking (bool): blocking。
            blocking_timeout (Optional[float]): blockingtimeout。
            thread_local (bool): threadlocal。
        """
        self.redis = redis
        self.name = name
        self.timeout = timeout
        self.sleep = sleep
        self.blocking = blocking
        self.blocking_timeout = blocking_timeout
        self.thread_local = bool(thread_local)
        self.local = threading.local() if self.thread_local else SimpleNamespace()
        self.local.token = None
        self.register_scripts()

    def register_scripts(self):
        """处理registerscripts相关逻辑。"""
        cls = self.__class__
        client = self.redis
        if cls.lua_release is None:
            cls.lua_release = client.register_script(cls.LUA_RELEASE_SCRIPT)
        if cls.lua_extend is None:
            cls.lua_extend = client.register_script(cls.LUA_EXTEND_SCRIPT)
        if cls.lua_reacquire is None:
            cls.lua_reacquire = client.register_script(cls.LUA_REACQUIRE_SCRIPT)

    async def __aenter__(self):
        """实现 __aenter__ 特殊方法。"""
        if await self.acquire():
            return self
        raise LockError("Unable to acquire lock within the time specified")

    async def __aexit__(self, exc_type, exc_value, traceback):
        """实现 __aexit__ 特殊方法。

        参数:
            exc_type (Any): exctype。
            exc_value (Any): excvalue。
            traceback (Any): traceback。
        """
        await self.release()

    async def acquire(
        self,
        blocking: Optional[bool] = None,
        blocking_timeout: Optional[float] = None,
        token: Optional[Union[str, bytes]] = None,
    ):
        """Use Redis to hold a shared, distributed lock named ``name``.

        参数:
            blocking (Optional[bool]): blocking。
            blocking_timeout (Optional[float]): blockingtimeout。
            token (Optional[Union[str, bytes]]): 令牌。
        """
        loop = asyncio.get_event_loop()
        sleep = self.sleep
        if token is None:
            token = uuid.uuid1().hex.encode()
        else:
            encoder = self.redis.connection_pool.get_encoder()
            token = encoder.encode(token)
        if blocking is None:
            blocking = self.blocking
        if blocking_timeout is None:
            blocking_timeout = self.blocking_timeout
        stop_trying_at = None
        if blocking_timeout is not None:
            stop_trying_at = loop.time() + blocking_timeout
        while True:
            if await self.do_acquire(token):
                self.local.token = token
                return True
            if not blocking:
                return False
            next_try_at = loop.time() + sleep
            if stop_trying_at is not None and next_try_at > stop_trying_at:
                return False
            await asyncio.sleep(sleep)

    async def do_acquire(self, token: Union[str, bytes]) -> bool:
        """处理doacquire相关逻辑。

        参数:
            token (Union[str, bytes]): 令牌。

        返回:
            bool: 表示是否成功。
        """
        if self.timeout:
            # convert to milliseconds
            timeout = int(self.timeout * 1000)
        else:
            timeout = None
        if await self.redis.set(self.name, token, nx=True, px=timeout):
            return True
        return False

    async def locked(self) -> bool:
        """处理locked相关逻辑。"""
        return await self.redis.get(self.name) is not None

    async def owned(self) -> bool:
        """处理owned相关逻辑。"""
        stored_token = await self.redis.get(self.name)
        # need to always compare bytes to bytes
        # TODO: this can be simplified when the context manager is finished
        if stored_token and not isinstance(stored_token, bytes):
            encoder = self.redis.connection_pool.get_encoder()
            stored_token = encoder.encode(stored_token)
        return self.local.token is not None and stored_token == self.local.token

    def release(self) -> Awaitable[NoReturn]:
        """处理release相关逻辑。"""
        expected_token = self.local.token
        if expected_token is None:
            raise LockError("Cannot release an unlocked lock")
        self.local.token = None
        return self.do_release(expected_token)

    async def do_release(self, expected_token: bytes):
        """处理dorelease相关逻辑。

        参数:
            expected_token (bytes): expected令牌。
        """
        if not bool(await self.lua_release(keys=[self.name], args=[expected_token], client=self.redis)):
            raise LockNotOwnedError("Cannot release a lock" " that's no longer owned")

    def extend(self, additional_time: float, replace_ttl: bool = False) -> Awaitable[bool]:
        """Adds more time to an already acquired lock.

        参数:
            additional_time (float): additional时间。
            replace_ttl (bool): replacettl。

        返回:
            Awaitable[bool]: 返回处理结果。
        """
        if self.local.token is None:
            raise LockError("Cannot extend an unlocked lock")
        if self.timeout is None:
            raise LockError("Cannot extend a lock with no timeout")
        return self.do_extend(additional_time, replace_ttl)

    async def do_extend(self, additional_time, replace_ttl) -> bool:
        """处理doextend相关逻辑。

        参数:
            additional_time (Any): additional时间。
            replace_ttl (Any): replacettl。

        返回:
            bool: 表示是否成功。
        """
        additional_time = int(additional_time * 1000)
        if not bool(
            await self.lua_extend(
                keys=[self.name],
                args=[self.local.token, additional_time, replace_ttl and "1" or "0"],
                client=self.redis,
            )
        ):
            raise LockNotOwnedError("Cannot extend a lock that's" " no longer owned")
        return True

    def reacquire(self) -> Awaitable[bool]:
        """处理reacquire相关逻辑。"""
        if self.local.token is None:
            raise LockError("Cannot reacquire an unlocked lock")
        if self.timeout is None:
            raise LockError("Cannot reacquire a lock with no timeout")
        return self.do_reacquire()

    async def do_reacquire(self) -> bool:
        """处理doreacquire相关逻辑。"""
        timeout = int(self.timeout * 1000)
        if not bool(await self.lua_reacquire(keys=[self.name], args=[self.local.token, timeout], client=self.redis)):
            raise LockNotOwnedError("Cannot reacquire a lock that's" " no longer owned")
        return True
