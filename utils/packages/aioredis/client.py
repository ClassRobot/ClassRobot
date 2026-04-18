import re
import asyncio
import hashlib
import inspect
import datetime
import warnings
import time as mod_time
from typing import (
    Any,
    Set,
    Dict,
    List,
    Type,
    Tuple,
    Union,
    Mapping,
    TypeVar,
    Callable,
    Iterable,
    NoReturn,
    Optional,
    Sequence,
    Awaitable,
    ValuesView,
    AbstractSet,
    AsyncIterator,
    MutableMapping,
    cast,
)

from .lock import Lock
from .compat import Protocol, TypedDict
from .utils import safe_str, str_if_bytes
from .connection import Connection, EncodableT, SSLConnection, ConnectionPool, UnixDomainSocketConnection
from .exceptions import (
    DataError,
    RedisError,
    WatchError,
    ModuleError,
    PubSubError,
    TimeoutError,
    NoScriptError,
    ResponseError,
    ExecAbortError,
    ConnectionError,
)

AbsExpiryT = Union[int, datetime.datetime]
ExpiryT = Union[int, datetime.timedelta]
ZScoreBoundT = Union[float, str]  # str allows for the [ or ( prefix
BitfieldOffsetT = Union[int, str]  # str allows for #x syntax
_StringLikeT = Union[bytes, str, memoryview]
KeyT = _StringLikeT  # Main redis key space
PatternT = _StringLikeT  # Patterns matched against keys, fields etc
FieldT = EncodableT  # Fields within hash tables, streams and geo commands
KeysT = Union[KeyT, Sequence[KeyT]]
ChannelT = _StringLikeT
GroupT = _StringLikeT  # Consumer group
ConsumerT = _StringLikeT  # Consumer name
StreamIdT = Union[int, _StringLikeT]
ScriptTextT = _StringLikeT
TimeoutSecT = Union[int, float, _StringLikeT]
# Mapping is not covariant in the key type, which prevents
# Mapping[_StringLikeT, X from accepting arguments of type Dict[str, X]. Using
# a TypeVar instead of a Union allows mappings with any of the permitted types
# to be passed. Care is needed if there is more than one such mapping in a
# type signature because they will all be required to be the same key type.
AnyKeyT = TypeVar("AnyKeyT", bytes, str, memoryview)
AnyFieldT = TypeVar("AnyFieldT", bytes, str, memoryview)
AnyChannelT = ChannelT
PubSubHandler = Callable[[Dict[str, str]], Awaitable[None]]

SYM_EMPTY = b""
EMPTY_RESPONSE = "EMPTY_RESPONSE"

_KeyT = TypeVar("_KeyT", bound=KeyT)
_ArgT = TypeVar("_ArgT", KeyT, EncodableT)
_RedisT = TypeVar("_RedisT", bound="Redis")
_NormalizeKeysT = TypeVar("_NormalizeKeysT", bound=Mapping[ChannelT, object])


def list_or_args(keys: Union[_KeyT, Iterable[_KeyT]], args: Optional[Iterable[_ArgT]]) -> List[Union[_KeyT, _ArgT]]:
    # returns a single new list combining keys and args
    """处理listargs相关逻辑。"""
    key_list: List[Union[_KeyT, _ArgT]]
    try:
        iter(keys)  # type: ignore[arg-type]
        keys = cast(Iterable[_KeyT], keys)
        # a string or bytes instance can be iterated, but indicates
        # keys wasn't passed as a list
        if isinstance(keys, (bytes, str)):
            key_list = [keys]
        else:
            key_list = list(keys)
    except TypeError:
        key_list = [cast(memoryview, keys)]
    if args:
        key_list.extend(args)
    return key_list


def timestamp_to_datetime(response):
    """处理timestampdatetime相关逻辑。"""
    if not response:
        return None
    try:
        response = int(response)
    except ValueError:
        return None
    return datetime.datetime.fromtimestamp(response)


def string_keys_to_dict(key_string, callback):
    """处理stringkeysdict相关逻辑。"""
    return dict.fromkeys(key_string.split(), callback)


class CaseInsensitiveDict(dict):
    """Case insensitive dict implementation. Assumes string keys only."""

    def __init__(self, data):
        """初始化实例。

        参数:
            data (Any): data。
        """
        for k, v in data.items():
            self[k.upper()] = v

    def __contains__(self, k):
        """实现 __contains__ 特殊方法。

        参数:
            k (Any): k。
        """
        return super().__contains__(k.upper())

    def __delitem__(self, k):
        """实现 __delitem__ 特殊方法。

        参数:
            k (Any): k。
        """
        super().__delitem__(k.upper())

    def __getitem__(self, k):
        """获取指定项。

        参数:
            k (Any): k。
        """
        return super().__getitem__(k.upper())

    def get(self, k, default=None):
        """处理获取相关逻辑。

        参数:
            k (Any): k。
            default (Any): default。
        """
        return super().get(k.upper(), default)

    def __setitem__(self, k, v):
        """设置指定项。

        参数:
            k (Any): k。
            v (Any): v。
        """
        super().__setitem__(k.upper(), v)

    def update(self, data):
        """更新当前数据。

        参数:
            data (Any): data。
        """
        data = CaseInsensitiveDict(data)
        super().update(data)


def parse_debug_object(response):
    """解析debugobject。"""
    # The 'type' of the object is the first item in the response, but isn't
    # prefixed with a name
    response = str_if_bytes(response)
    response = "type:" + response
    response = dict(kv.split(":") for kv in response.split())

    # parse some expected int values from the string response
    # note: this cmd isn't spec'd so these may not appear in all redis versions
    int_fields = ("refcount", "serializedlength", "lru", "lru_seconds_idle")
    for field in int_fields:
        if field in response:
            response[field] = int(response[field])

    return response


def parse_object(response, infotype):
    """解析object。"""
    if infotype in ("idletime", "refcount"):
        return int_or_none(response)
    return response


def parse_info(response):
    """解析info。"""
    info: Dict[str, Any] = {}
    response = str_if_bytes(response)

    def get_value(value):
        """获取value。"""
        if "," not in value or "=" not in value:
            try:
                if "." in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                return value
        else:
            sub_dict = {}
            for item in value.split(","):
                k, v = item.rsplit("=", 1)
                sub_dict[k] = get_value(v)
            return sub_dict

    for line in response.splitlines():
        if line and not line.startswith("#"):
            if line.find(":") != -1:
                # Split, the info fields keys and values.
                # Note that the value may contain ':'. but the 'host:'
                # pseudo-command is the only case where the key contains ':'
                key, value = line.split(":", 1)
                if key == "cmdstat_host":
                    key, value = line.rsplit(":", 1)

                if key == "module":
                    # Hardcode a list for key 'modules' since there could be
                    # multiple lines that started with 'module'
                    info.setdefault("modules", []).append(get_value(value))
                else:
                    info[key] = get_value(value)
            else:
                # if the line isn't splittable, append it to the "__raw__" key
                info.setdefault("__raw__", []).append(line)

    return info


def parse_memory_stats(response, **kwargs):
    """解析memorystats。"""
    stats = pairs_to_dict(response, decode_keys=True, decode_string_values=True)
    for key, value in stats.items():
        if key.startswith("db."):
            stats[key] = pairs_to_dict(value, decode_keys=True, decode_string_values=True)
    return stats


SENTINEL_STATE_TYPES = {
    "can-failover-its-master": int,
    "config-epoch": int,
    "down-after-milliseconds": int,
    "failover-timeout": int,
    "info-refresh": int,
    "last-hello-message": int,
    "last-ok-ping-reply": int,
    "last-ping-reply": int,
    "last-ping-sent": int,
    "master-link-down-time": int,
    "master-port": int,
    "num-other-sentinels": int,
    "num-slaves": int,
    "o-down-time": int,
    "pending-commands": int,
    "parallel-syncs": int,
    "port": int,
    "quorum": int,
    "role-reported-time": int,
    "s-down-time": int,
    "slave-priority": int,
    "slave-repl-offset": int,
    "voted-leader-epoch": int,
}


def parse_sentinel_state(item):
    """解析sentinelstate。"""
    result = pairs_to_dict_typed(item, SENTINEL_STATE_TYPES)
    flags = set(result["flags"].split(","))
    for name, flag in (
        ("is_master", "master"),
        ("is_slave", "slave"),
        ("is_sdown", "s_down"),
        ("is_odown", "o_down"),
        ("is_sentinel", "sentinel"),
        ("is_disconnected", "disconnected"),
        ("is_master_down", "master_down"),
    ):
        result[name] = flag in flags
    return result


def parse_sentinel_master(response):
    """解析sentinelmaster。"""
    return parse_sentinel_state(map(str_if_bytes, response))


def parse_sentinel_masters(response):
    """解析sentinelmasters。"""
    result = {}
    for item in response:
        state = parse_sentinel_state(map(str_if_bytes, item))
        result[state["name"]] = state
    return result


def parse_sentinel_slaves_and_sentinels(response):
    """解析sentinelslavesandsentinels。"""
    return [parse_sentinel_state(map(str_if_bytes, item)) for item in response]


def parse_sentinel_get_master(response):
    """解析sentinelgetmaster。"""
    return response and (response[0], int(response[1])) or None


def pairs_to_dict(response, decode_keys=False, decode_string_values=False):
    """处理pairsdict相关逻辑。"""
    if response is None:
        return {}
    if decode_keys or decode_string_values:
        # the iter form is faster, but I don't know how to make that work
        # with a str_if_bytes() map
        keys = response[::2]
        if decode_keys:
            keys = map(str_if_bytes, keys)
        values = response[1::2]
        if decode_string_values:
            values = map(str_if_bytes, values)
        return dict(zip(keys, values))
    else:
        it = iter(response)
        return dict(zip(it, it))


def pairs_to_dict_typed(response, type_info):
    """处理pairsdicttyped相关逻辑。"""
    it = iter(response)
    result = {}
    for key, value in zip(it, it):
        if key in type_info:
            try:
                value = type_info[key](value)
            except Exception:
                # if for some reason the value can't be coerced, just use
                # the string value
                pass
        result[key] = value
    return result


def zset_score_pairs(response, **options):
    """
    If ``withscores`` is specified in the options, return the response as
    a list of (value, score) pairs
    """
    if not response or not options.get("withscores"):
        return response
    score_cast_func = options.get("score_cast_func", float)
    it = iter(response)
    return list(zip(it, map(score_cast_func, it)))


def sort_return_tuples(response, **options):
    """
    If ``groups`` is specified, return the response as a list of
    n-element tuples with n being the value found in options['groups']
    """
    if not response or not options.get("groups"):
        return response
    n = options["groups"]
    return list(zip(*(response[i::n] for i in range(n))))


def int_or_none(response):
    """处理intnone相关逻辑。"""
    if response is None:
        return None
    return int(response)


def parse_stream_list(response):
    """解析streamlist。"""
    if response is None:
        return None
    data = []
    for r in response:
        if r is not None:
            data.append((r[0], pairs_to_dict(r[1])))
        else:
            data.append((None, None))
    return data


def pairs_to_dict_with_str_keys(response):
    """处理pairsdictstrkeys相关逻辑。"""
    return pairs_to_dict(response, decode_keys=True)


def parse_list_of_dicts(response):
    """解析listdicts。"""
    return list(map(pairs_to_dict_with_str_keys, response))


def parse_xclaim(response, **options):
    """解析xclaim。"""
    if options.get("parse_justid", False):
        return response
    return parse_stream_list(response)


def parse_xinfo_stream(response):
    """解析xinfostream。"""
    data = pairs_to_dict(response, decode_keys=True)
    first = data["first-entry"]
    if first is not None:
        data["first-entry"] = (first[0], pairs_to_dict(first[1]))
    last = data["last-entry"]
    if last is not None:
        data["last-entry"] = (last[0], pairs_to_dict(last[1]))
    return data


def parse_xread(response):
    """解析xread。"""
    if response is None:
        return []
    return [[r[0], parse_stream_list(r[1])] for r in response]


def parse_xpending(response, **options):
    """解析xpending。"""
    if options.get("parse_detail", False):
        return parse_xpending_range(response)
    consumers = [{"name": n, "pending": int(p)} for n, p in response[3] or []]
    return {
        "pending": response[0],
        "min": response[1],
        "max": response[2],
        "consumers": consumers,
    }


def parse_xpending_range(response):
    """解析xpendingrange。"""
    k = ("message_id", "consumer", "time_since_delivered", "times_delivered")
    return [dict(zip(k, r)) for r in response]


def float_or_none(response):
    """处理floatnone相关逻辑。"""
    if response is None:
        return None
    return float(response)


def bool_ok(response):
    """处理boolok相关逻辑。"""
    return str_if_bytes(response) == "OK"


def parse_zadd(response, **options):
    """解析zadd。"""
    if response is None:
        return None
    if options.get("as_score"):
        return float(response)
    return int(response)


def parse_client_list(response, **options):
    """解析clientlist。"""
    clients = []
    for c in str_if_bytes(response).splitlines():
        # Values might contain '='
        clients.append(dict(pair.split("=", 1) for pair in c.split(" ")))
    return clients


def parse_config_get(response, **options):
    """解析配置获取。"""
    response = [str_if_bytes(i) if i is not None else None for i in response]
    return response and pairs_to_dict(response) or {}


def parse_scan(response, **options):
    """解析scan。"""
    cursor, r = response
    return int(cursor), r


def parse_hscan(response, **options):
    """解析hscan。"""
    cursor, r = response
    return int(cursor), r and pairs_to_dict(r) or {}


def parse_zscan(response, **options):
    """解析zscan。"""
    score_cast_func = options.get("score_cast_func", float)
    cursor, r = response
    it = iter(r)
    return int(cursor), list(zip(it, map(score_cast_func, it)))


def parse_slowlog_get(response, **options):
    """解析slowlogget。"""
    space: Union[str, bytes] = " " if options.get("decode_responses", False) else b" "
    return [
        {
            "id": item[0],
            "start_time": int(item[1]),
            "duration": int(item[2]),
            # Redis Enterprise injects another entry at index [3], which has
            # the complexity info (i.e. the value N in case the command has
            # an O(N) complexity) instead of the command.
            "command": (space.join(item[3]) if isinstance(item[3], list) else space.join(item[4])),
        }
        for item in response
    ]


def parse_cluster_info(response, **options):
    """解析clusterinfo。"""
    response = str_if_bytes(response)
    return dict(line.split(":") for line in response.splitlines() if line)


def _parse_node_line(line):
    """处理parsenodeline相关逻辑。"""
    line_items = line.split(" ")
    node_id, addr, flags, master_id, ping, pong, epoch, connected = line.split(" ")[:8]
    slots = [sl.split("-") for sl in line_items[8:]]
    node_dict = {
        "node_id": node_id,
        "flags": flags,
        "master_id": master_id,
        "last_ping_sent": ping,
        "last_pong_rcvd": pong,
        "epoch": epoch,
        "slots": slots,
        "connected": True if connected == "connected" else False,
    }
    return addr, node_dict


def parse_cluster_nodes(response, **options):
    """解析clusternodes。"""
    raw_lines = str_if_bytes(response).splitlines()
    return dict(_parse_node_line(line) for line in raw_lines)


def parse_georadius_generic(response, **options):
    """解析georadiusgeneric。"""
    if options["store"] or options["store_dist"]:
        # `store` and `store_diff` cant be combined
        # with other command arguments.
        return response

    if type(response) != list:
        response_list = [response]
    else:
        response_list = response

    if not options["withdist"] and not options["withcoord"] and not options["withhash"]:
        # just a bunch of places
        return response_list

    cast: Dict[str, Callable] = {
        "withdist": float,
        "withcoord": lambda ll: (float(ll[0]), float(ll[1])),
        "withhash": int,
    }

    # zip all output results with each casting functino to get
    # the properly native Python value.
    f = [lambda x: x]
    f += [cast[o] for o in ["withdist", "withhash", "withcoord"] if options[o]]
    return [list(map(lambda fv: fv[0](fv[1]), zip(f, r))) for r in response_list]


def parse_pubsub_numsub(response, **options):
    """解析pubsubnumsub。"""
    return list(zip(response[0::2], response[1::2]))


def parse_client_kill(response, **options):
    """解析clientkill。"""
    if isinstance(response, int):
        return response
    return str_if_bytes(response) == "OK"


def parse_acl_getuser(response, **options):
    """解析aclgetuser。"""
    if response is None:
        return None
    data = pairs_to_dict(response, decode_keys=True)

    # convert everything but user-defined data in 'keys' to native strings
    data["flags"] = list(map(str_if_bytes, data["flags"]))
    data["passwords"] = list(map(str_if_bytes, data["passwords"]))
    data["commands"] = str_if_bytes(data["commands"])

    # split 'commands' into separate 'categories' and 'commands' lists
    commands, categories = [], []
    for command in data["commands"].split(" "):
        if "@" in command:
            categories.append(command)
        else:
            commands.append(command)

    data["commands"] = commands
    data["categories"] = categories
    data["enabled"] = "on" in data["flags"]
    return data


def parse_acl_log(response, **options):
    """解析acllog。"""
    if response is None:
        return None
    if isinstance(response, list):
        data = []
        for log in response:
            log_data = pairs_to_dict(log, True, True)
            client_info = log_data.get("client-info", "")
            log_data["client-info"] = parse_client_info(client_info)

            # float() is lossy comparing to the "double" in C
            log_data["age-seconds"] = float(log_data["age-seconds"])
            data.append(log_data)
    else:
        data = bool_ok(response)
    return data


def parse_client_info(value):
    """
    Parsing client-info in ACL Log in following format.
    "key1=value1 key2=value2 key3=value3"
    """
    client_info = {}
    infos = value.split(" ")
    for info in infos:
        key, value = info.split("=")
        client_info[key] = value

    # Those fields are definded as int in networking.c
    for int_key in {
        "id",
        "age",
        "idle",
        "db",
        "sub",
        "psub",
        "multi",
        "qbuf",
        "qbuf-free",
        "obl",
        "oll",
        "omem",
    }:
        client_info[int_key] = int(client_info[int_key])
    return client_info


def parse_module_result(response):
    """解析moduleresult。"""
    if isinstance(response, ModuleError):
        raise response
    return True


class ResponseCallbackProtocol(Protocol):
    """定义responsecallbackprotocol协议接口。"""
    def __call__(self, response: Any, **kwargs):
        """调用实例并返回结果。

        参数:
            response (Any): response。
            kwargs (**Any): 可变关键字参数。
        """
        ...


class AsyncResponseCallbackProtocol(Protocol):
    """定义asyncresponsecallbackprotocol协议接口。"""
    async def __call__(self, response: Any, **kwargs):
        """调用实例并返回结果。

        参数:
            response (Any): response。
            kwargs (**Any): 可变关键字参数。
        """
        ...


ResponseCallbackT = Union[ResponseCallbackProtocol, AsyncResponseCallbackProtocol]


_R = TypeVar("_R")


class Redis:
    """
    Implementation of the Redis protocol.

    This abstract class provides a Python interface to all Redis commands
    and an implementation of the Redis protocol.

    Connection and Pipeline derive from this, implementing how
    the commands are sent and received to the Redis server
    """

    RESPONSE_CALLBACKS = {
        **string_keys_to_dict(
            "AUTH EXPIRE EXPIREAT HEXISTS HMSET MOVE MSETNX PERSIST " "PSETEX RENAMENX SISMEMBER SMOVE SETEX SETNX",
            bool,
        ),
        **string_keys_to_dict(
            "BITCOUNT BITPOS DECRBY DEL EXISTS GEOADD GETBIT HDEL HLEN "
            "HSTRLEN INCRBY LINSERT LLEN LPUSHX PFADD PFCOUNT RPUSHX SADD "
            "SCARD SDIFFSTORE SETBIT SETRANGE SINTERSTORE SREM STRLEN "
            "SUNIONSTORE UNLINK XACK XDEL XLEN XTRIM ZCARD ZLEXCOUNT ZREM "
            "ZREMRANGEBYLEX ZREMRANGEBYRANK ZREMRANGEBYSCORE",
            int,
        ),
        **string_keys_to_dict("INCRBYFLOAT HINCRBYFLOAT", float),
        **string_keys_to_dict(
            # these return OK, or int if redis-server is >=1.3.4
            "LPUSH RPUSH",
            lambda r: isinstance(r, int) and r or str_if_bytes(r) == "OK",
        ),
        **string_keys_to_dict("SORT", sort_return_tuples),
        **string_keys_to_dict("ZSCORE ZINCRBY GEODIST", float_or_none),
        **string_keys_to_dict(
            "FLUSHALL FLUSHDB LSET LTRIM MSET PFMERGE READONLY READWRITE "
            "RENAME SAVE SELECT SHUTDOWN SLAVEOF SWAPDB WATCH UNWATCH ",
            bool_ok,
        ),
        **string_keys_to_dict("BLPOP BRPOP", lambda r: r and tuple(r) or None),
        **string_keys_to_dict("SDIFF SINTER SMEMBERS SUNION", lambda r: r and set(r) or set()),
        **string_keys_to_dict(
            "ZPOPMAX ZPOPMIN ZRANGE ZRANGEBYSCORE ZREVRANGE ZREVRANGEBYSCORE",
            zset_score_pairs,
        ),
        **string_keys_to_dict("BZPOPMIN BZPOPMAX", lambda r: r and (r[0], r[1], float(r[2])) or None),
        **string_keys_to_dict("ZRANK ZREVRANK", int_or_none),
        **string_keys_to_dict("XREVRANGE XRANGE", parse_stream_list),
        **string_keys_to_dict("XREAD XREADGROUP", parse_xread),
        **string_keys_to_dict("BGREWRITEAOF BGSAVE", lambda r: True),
        "ACL CAT": lambda r: list(map(str_if_bytes, r)),
        "ACL DELUSER": int,
        "ACL GENPASS": str_if_bytes,
        "ACL GETUSER": parse_acl_getuser,
        "ACL LIST": lambda r: list(map(str_if_bytes, r)),
        "ACL LOAD": bool_ok,
        "ACL LOG": parse_acl_log,
        "ACL SAVE": bool_ok,
        "ACL SETUSER": bool_ok,
        "ACL USERS": lambda r: list(map(str_if_bytes, r)),
        "ACL WHOAMI": str_if_bytes,
        "CLIENT GETNAME": str_if_bytes,
        "CLIENT ID": int,
        "CLIENT KILL": parse_client_kill,
        "CLIENT LIST": parse_client_list,
        "CLIENT SETNAME": bool_ok,
        "CLIENT UNBLOCK": lambda r: r and int(r) == 1 or False,
        "CLIENT PAUSE": bool_ok,
        "CLUSTER ADDSLOTS": bool_ok,
        "CLUSTER COUNT-FAILURE-REPORTS": lambda x: int(x),
        "CLUSTER COUNTKEYSINSLOT": lambda x: int(x),
        "CLUSTER DELSLOTS": bool_ok,
        "CLUSTER FAILOVER": bool_ok,
        "CLUSTER FORGET": bool_ok,
        "CLUSTER INFO": parse_cluster_info,
        "CLUSTER KEYSLOT": lambda x: int(x),
        "CLUSTER MEET": bool_ok,
        "CLUSTER NODES": parse_cluster_nodes,
        "CLUSTER REPLICATE": bool_ok,
        "CLUSTER RESET": bool_ok,
        "CLUSTER SAVECONFIG": bool_ok,
        "CLUSTER SET-CONFIG-EPOCH": bool_ok,
        "CLUSTER SETSLOT": bool_ok,
        "CLUSTER SLAVES": parse_cluster_nodes,
        "CONFIG GET": parse_config_get,
        "CONFIG RESETSTAT": bool_ok,
        "CONFIG SET": bool_ok,
        "DEBUG OBJECT": parse_debug_object,
        "GEOHASH": lambda r: list(map(str_if_bytes, r)),
        "GEOPOS": lambda r: list(map(lambda ll: (float(ll[0]), float(ll[1])) if ll is not None else None, r)),
        "GEORADIUS": parse_georadius_generic,
        "GEORADIUSBYMEMBER": parse_georadius_generic,
        "HGETALL": lambda r: r and pairs_to_dict(r) or {},
        "HSCAN": parse_hscan,
        "INFO": parse_info,
        "LASTSAVE": timestamp_to_datetime,
        "MEMORY PURGE": bool_ok,
        "MEMORY STATS": parse_memory_stats,
        "MEMORY USAGE": int_or_none,
        "MODULE LOAD": parse_module_result,
        "MODULE UNLOAD": parse_module_result,
        "MODULE LIST": lambda r: [pairs_to_dict(m) for m in r],
        "OBJECT": parse_object,
        "PING": lambda r: str_if_bytes(r) == "PONG",
        "PUBSUB NUMSUB": parse_pubsub_numsub,
        "RANDOMKEY": lambda r: r and r or None,
        "SCAN": parse_scan,
        "SCRIPT EXISTS": lambda r: list(map(bool, r)),
        "SCRIPT FLUSH": bool_ok,
        "SCRIPT KILL": bool_ok,
        "SCRIPT LOAD": str_if_bytes,
        "SENTINEL GET-MASTER-ADDR-BY-NAME": parse_sentinel_get_master,
        "SENTINEL MASTER": parse_sentinel_master,
        "SENTINEL MASTERS": parse_sentinel_masters,
        "SENTINEL MONITOR": bool_ok,
        "SENTINEL REMOVE": bool_ok,
        "SENTINEL SENTINELS": parse_sentinel_slaves_and_sentinels,
        "SENTINEL SET": bool_ok,
        "SENTINEL SLAVES": parse_sentinel_slaves_and_sentinels,
        "SET": lambda r: r and str_if_bytes(r) == "OK",
        "SLOWLOG GET": parse_slowlog_get,
        "SLOWLOG LEN": int,
        "SLOWLOG RESET": bool_ok,
        "SSCAN": parse_scan,
        "TIME": lambda x: (int(x[0]), int(x[1])),
        "XCLAIM": parse_xclaim,
        "XGROUP CREATE": bool_ok,
        "XGROUP DELCONSUMER": int,
        "XGROUP DESTROY": bool,
        "XGROUP SETID": bool_ok,
        "XINFO CONSUMERS": parse_list_of_dicts,
        "XINFO GROUPS": parse_list_of_dicts,
        "XINFO STREAM": parse_xinfo_stream,
        "XPENDING": parse_xpending,
        "ZADD": parse_zadd,
        "ZSCAN": parse_zscan,
    }

    response_callbacks: MutableMapping[Union[str, bytes], ResponseCallbackT]

    @classmethod
    def from_url(cls, url: str, **kwargs):
        """Return a Redis client object configured from the given URL

        参数:
            url (str): 资源链接。
            kwargs (**Any): 可变关键字参数。
        """
        connection_pool = ConnectionPool.from_url(url, **kwargs)
        return cls(connection_pool=connection_pool)

    def __init__(
        self,
        *,
        host: str = "localhost",
        port: int = 6379,
        db: Union[str, int] = 0,
        password: Optional[str] = None,
        socket_timeout: Optional[float] = None,
        socket_connect_timeout: Optional[float] = None,
        socket_keepalive: Optional[bool] = None,
        socket_keepalive_options: Optional[Mapping[int, Union[int, bytes]]] = None,
        connection_pool: Optional[ConnectionPool] = None,
        unix_socket_path: Optional[str] = None,
        encoding: str = "utf-8",
        encoding_errors: str = "strict",
        decode_responses: bool = False,
        retry_on_timeout: bool = False,
        ssl: bool = False,
        ssl_keyfile: Optional[str] = None,
        ssl_certfile: Optional[str] = None,
        ssl_cert_reqs: str = "required",
        ssl_ca_certs: Optional[str] = None,
        ssl_check_hostname: bool = False,
        max_connections: Optional[int] = None,
        single_connection_client: bool = False,
        health_check_interval: int = 0,
        client_name: Optional[str] = None,
        username: Optional[str] = None,
        auto_close_connection_pool: bool = True,
    ):
        """初始化实例。

        参数:
            host (str): host。
            port (int): port。
            db (Union[str, int]): db。
            password (Optional[str]): 密码。
            socket_timeout (Optional[float]): sockettimeout。
            socket_connect_timeout (Optional[float]): socketconnecttimeout。
            socket_keepalive (Optional[bool]): socketkeepalive。
            socket_keepalive_options (Optional[Mapping[int, Union[int, bytes]]]): socketkeepaliveoptions。
            connection_pool (Optional[ConnectionPool]): connectionpool。
            unix_socket_path (Optional[str]): unixsocket路径。
            encoding (str): encoding。
            encoding_errors (str): encodingerrors。
            decode_responses (bool): decoderesponses。
            retry_on_timeout (bool): retryontimeout。
            ssl (bool): ssl。
            ssl_keyfile (Optional[str]): sslkeyfile。
            ssl_certfile (Optional[str]): sslcertfile。
            ssl_cert_reqs (str): sslcertreqs。
            ssl_ca_certs (Optional[str]): sslcacerts。
            ssl_check_hostname (bool): ssl检查hostname。
            max_connections (Optional[int]): maxconnections。
            single_connection_client (bool): singleconnectionclient。
            health_check_interval (int): health检查interval。
            client_name (Optional[str]): client名称。
            username (Optional[str]): 用户名。
            auto_close_connection_pool (bool): autocloseconnectionpool。
        """
        kwargs: Dict[str, Any]
        # auto_close_connection_pool only has an effect if connection_pool is
        # None. This is a similar feature to the missing __del__ to resolve #1103,
        # but it accounts for whether a user wants to manually close the connection
        # pool, as a similar feature to ConnectionPool's __del__.
        self.auto_close_connection_pool = auto_close_connection_pool if connection_pool is None else False
        if not connection_pool:
            kwargs = {
                "db": db,
                "username": username,
                "password": password,
                "socket_timeout": socket_timeout,
                "encoding": encoding,
                "encoding_errors": encoding_errors,
                "decode_responses": decode_responses,
                "retry_on_timeout": retry_on_timeout,
                "max_connections": max_connections,
                "health_check_interval": health_check_interval,
                "client_name": client_name,
            }
            # based on input, setup appropriate connection args
            if unix_socket_path is not None:
                kwargs.update(
                    {
                        "path": unix_socket_path,
                        "connection_class": UnixDomainSocketConnection,
                    }
                )
            else:
                # TCP specific options
                kwargs.update(
                    {
                        "host": host,
                        "port": port,
                        "socket_connect_timeout": socket_connect_timeout,
                        "socket_keepalive": socket_keepalive,
                        "socket_keepalive_options": socket_keepalive_options,
                    }
                )

                if ssl:
                    kwargs.update(
                        {
                            "connection_class": SSLConnection,
                            "ssl_keyfile": ssl_keyfile,
                            "ssl_certfile": ssl_certfile,
                            "ssl_cert_reqs": ssl_cert_reqs,
                            "ssl_ca_certs": ssl_ca_certs,
                            "ssl_check_hostname": ssl_check_hostname,
                        }
                    )
            connection_pool = ConnectionPool(**kwargs)
        self.connection_pool = connection_pool
        self.single_connection_client = single_connection_client
        self.connection: Optional[Connection] = None

        self.response_callbacks = CaseInsensitiveDict(self.__class__.RESPONSE_CALLBACKS)

    def __repr__(self):
        """返回调试字符串表示。"""
        return f"{self.__class__.__name__}<{self.connection_pool!r}>"

    def __await__(self):
        """返回可等待对象。"""
        return self.initialize().__await__()

    async def initialize(self: _RedisT) -> _RedisT:
        """处理initialize相关逻辑。"""
        if self.single_connection_client and self.connection is None:
            self.connection = await self.connection_pool.get_connection("_")
        return self

    def set_response_callback(self, command: str, callback: ResponseCallbackT):
        """设置responsecallback。

        参数:
            command (str): command。
            callback (ResponseCallbackT): callback。
        """
        self.response_callbacks[command] = callback

    def pipeline(self, transaction: bool = True, shard_hint: Optional[str] = None) -> "Pipeline":
        """Return a new pipeline object that can queue multiple commands for

        参数:
            transaction (bool): transaction。
            shard_hint (Optional[str]): shardhint。

        返回:
            'Pipeline': 返回处理结果。
        """
        return Pipeline(self.connection_pool, self.response_callbacks, transaction, shard_hint)

    async def transaction(
        self,
        func: Callable[["Pipeline"], Union[Any, Awaitable[Any]]],
        *watches: KeyT,
        shard_hint: Optional[str] = None,
        value_from_callable: bool = False,
        watch_delay: Optional[float] = None,
    ):
        """Convenience method for executing the callable `func` as a transaction

        参数:
            func (Callable[['Pipeline'], Union[Any, Awaitable[Any]]]): func。
            shard_hint (Optional[str]): shardhint。
            value_from_callable (bool): valuefromcallable。
            watch_delay (Optional[float]): watchdelay。
            watches (*KeyT): watches。
        """
        pipe: Pipeline
        async with self.pipeline(True, shard_hint) as pipe:
            while True:
                try:
                    if watches:
                        await pipe.watch(*watches)
                    func_value = func(pipe)
                    if inspect.isawaitable(func_value):
                        func_value = await func_value
                    exec_value = await pipe.execute()
                    return func_value if value_from_callable else exec_value
                except WatchError:
                    if watch_delay is not None and watch_delay > 0:
                        await asyncio.sleep(watch_delay)
                    continue

    def lock(
        self,
        name: KeyT,
        timeout: Optional[float] = None,
        sleep: float = 0.1,
        blocking_timeout: Optional[float] = None,
        lock_class: Optional[Type[Lock]] = None,
        thread_local=True,
    ) -> Lock:
        """Return a new Lock object using key ``name`` that mimics

        参数:
            name (KeyT): 名称。
            timeout (Optional[float]): timeout。
            sleep (float): sleep。
            blocking_timeout (Optional[float]): blockingtimeout。
            lock_class (Optional[Type[Lock]]): lock班级。
            thread_local (Any): threadlocal。

        返回:
            Lock: 返回处理结果。
        """
        if lock_class is None:
            lock_class = Lock
        return lock_class(
            self,
            name,
            timeout=timeout,
            sleep=sleep,
            blocking_timeout=blocking_timeout,
            thread_local=thread_local,
        )

    def pubsub(self, **kwargs) -> "PubSub":
        """Return a Publish/Subscribe object. With this object, you can

        参数:
            kwargs (**Any): 可变关键字参数。

        返回:
            'PubSub': 返回处理结果。
        """
        return PubSub(self.connection_pool, **kwargs)

    def monitor(self) -> "Monitor":
        """处理monitor相关逻辑。"""
        return Monitor(self.connection_pool)

    def client(self) -> "Redis":
        """处理client相关逻辑。"""
        return self.__class__(connection_pool=self.connection_pool, single_connection_client=True)

    async def __aenter__(self: _RedisT) -> _RedisT:
        """实现 __aenter__ 特殊方法。"""
        return await self.initialize()

    async def __aexit__(self, exc_type, exc_value, traceback):
        """实现 __aexit__ 特殊方法。

        参数:
            exc_type (Any): exctype。
            exc_value (Any): excvalue。
            traceback (Any): traceback。
        """
        await self.close()

    _DEL_MESSAGE = "Unclosed Redis client"

    def __del__(self, _warnings: Any = warnings) -> None:
        """实现 __del__ 特殊方法。

        参数:
            _warnings (Any): warnings。
        """
        if self.connection is not None:
            _warnings.warn(
                f"Unclosed client session {self!r}",
                ResourceWarning,
                source=self,
            )
            context = {"client": self, "message": self._DEL_MESSAGE}
            asyncio.get_event_loop().call_exception_handler(context)

    async def close(self, close_connection_pool: Optional[bool] = None) -> None:
        """Closes Redis client connection

        参数:
            close_connection_pool (Optional[bool]): closeconnectionpool。
        """
        conn = self.connection
        if conn:
            self.connection = None
            await self.connection_pool.release(conn)
        if close_connection_pool or (close_connection_pool is None and self.auto_close_connection_pool):
            await self.connection_pool.disconnect()

    # COMMAND EXECUTION AND PROTOCOL PARSING
    async def execute_command(self, *args, **options):
        """处理executecommand相关逻辑。

        参数:
            args (*Any): 可变位置参数。
            options (**Any): options。
        """
        await self.initialize()
        pool = self.connection_pool
        command_name = args[0]
        conn = self.connection or await pool.get_connection(command_name, **options)
        try:
            await conn.send_command(*args)
            return await self.parse_response(conn, command_name, **options)
        except (ConnectionError, TimeoutError) as e:
            await conn.disconnect()
            if not (conn.retry_on_timeout and isinstance(e, TimeoutError)):
                raise
            await conn.send_command(*args)
            return await self.parse_response(conn, command_name, **options)
        finally:
            if not self.connection:
                await pool.release(conn)

    async def parse_response(self, connection: Connection, command_name: Union[str, bytes], **options):
        """解析response。

        参数:
            connection (Connection): connection。
            command_name (Union[str, bytes]): command名称。
            options (**Any): options。
        """
        try:
            response = await connection.read_response()
        except ResponseError:
            if EMPTY_RESPONSE in options:
                return options[EMPTY_RESPONSE]
            raise
        if command_name in self.response_callbacks:
            # Mypy bug: https://github.com/python/mypy/issues/10977
            command_name = cast(str, command_name)
            retval = self.response_callbacks[command_name](response, **options)
            return await retval if inspect.isawaitable(retval) else retval
        return response

    # SERVER INFORMATION

    # ACL methods
    def acl_cat(self, category: Optional[str] = None) -> Awaitable:
        """Returns a list of categories or commands within a category.

        参数:
            category (Optional[str]): category。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [category] if category else []
        return self.execute_command("ACL CAT", *pieces)

    def acl_deluser(self, username: str) -> Awaitable:
        """处理acldeluser相关逻辑。

        参数:
            username (str): 用户名。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ACL DELUSER", username)

    def acl_genpass(self) -> Awaitable:
        """处理aclgenpass相关逻辑。"""
        return self.execute_command("ACL GENPASS")

    def acl_getuser(self, username: str) -> Awaitable:
        """Get the ACL details for the specified ``username``.

        参数:
            username (str): 用户名。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ACL GETUSER", username)

    def acl_list(self) -> Awaitable:
        """处理acllist相关逻辑。"""
        return self.execute_command("ACL LIST")

    def acl_log(self, count: Optional[int] = None) -> Awaitable:
        """Get ACL logs as a list.

        参数:
            count (Optional[int]): 统计。

        返回:
            Awaitable: 返回处理结果。
        """
        args = []
        if count is not None:
            if not isinstance(count, int):
                raise DataError("ACL LOG count must be an integer")
            args.append(count)

        return self.execute_command("ACL LOG", *args)

    def acl_log_reset(self) -> Awaitable:
        """
        Reset ACL logs.
        :rtype: Boolean.
        """
        args = [b"RESET"]
        return self.execute_command("ACL LOG", *args)

    def acl_load(self) -> Awaitable:
        """
        Load ACL rules from the configured ``aclfile``.

        Note that the server must be configured with the ``aclfile``
        directive to be able to load ACL rules from an aclfile.
        """
        return self.execute_command("ACL LOAD")

    def acl_save(self) -> Awaitable:
        """
        Save ACL rules to the configured ``aclfile``.

        Note that the server must be configured with the ``aclfile``
        directive to be able to save ACL rules to an aclfile.
        """
        return self.execute_command("ACL SAVE")

    def acl_setuser(  # noqa: C901
        self,
        username: str,
        enabled: bool = False,
        nopass: bool = False,
        passwords: Optional[Union[str, Iterable[str]]] = None,
        hashed_passwords: Optional[Union[str, Iterable[str]]] = None,
        categories: Optional[Iterable[str]] = None,
        commands: Optional[Iterable[str]] = None,
        keys: Optional[Iterable[KeyT]] = None,
        reset: bool = False,
        reset_keys: bool = False,
        reset_passwords: bool = False,
    ) -> Awaitable:
        """Create or update an ACL user.

        参数:
            username (str): 用户名。
            enabled (bool): enabled。
            nopass (bool): nopass。
            passwords (Optional[Union[str, Iterable[str]]]): passwords。
            hashed_passwords (Optional[Union[str, Iterable[str]]]): hashedpasswords。
            categories (Optional[Iterable[str]]): categories。
            commands (Optional[Iterable[str]]): commands。
            keys (Optional[Iterable[KeyT]]): keys。
            reset (bool): reset。
            reset_keys (bool): resetkeys。
            reset_passwords (bool): resetpasswords。

        返回:
            Awaitable: 返回处理结果。
        """
        encoder = self.connection_pool.get_encoder()
        pieces: List[Union[str, bytes]] = [username]

        if reset:
            pieces.append(b"reset")

        if reset_keys:
            pieces.append(b"resetkeys")

        if reset_passwords:
            pieces.append(b"resetpass")

        if enabled:
            pieces.append(b"on")
        else:
            pieces.append(b"off")

        if (passwords or hashed_passwords) and nopass:
            raise DataError("Cannot set 'nopass' and supply " "'passwords' or 'hashed_passwords'")

        if passwords:
            # as most users will have only one password, allow remove_passwords
            # to be specified as a simple string or a list
            converted_passwords = list_or_args(passwords, [])
            for i, raw_password in enumerate(converted_passwords):
                password = encoder.encode(raw_password)
                if password.startswith(b"+"):
                    pieces.append(b">%s" % password[1:])
                elif password.startswith(b"-"):
                    pieces.append(b"<%s" % password[1:])
                else:
                    raise DataError("Password %d must be prefixeed with a " '"+" to add or a "-" to remove' % i)

        if hashed_passwords:
            # as most users will have only one password, allow remove_passwords
            # to be specified as a simple string or a list
            parsed_hashed_passwords = list_or_args(hashed_passwords, [])
            for i, raw_hashed_password in enumerate(parsed_hashed_passwords):
                hashed_password = encoder.encode(raw_hashed_password)
                if hashed_password.startswith(b"+"):
                    pieces.append(b"#%s" % hashed_password[1:])
                elif hashed_password.startswith(b"-"):
                    pieces.append(b"!%s" % hashed_password[1:])
                else:
                    raise DataError("Hashed %d password must be prefixeed " 'with a "+" to add or a "-" to remove' % i)

        if nopass:
            pieces.append(b"nopass")

        if categories:
            for raw_category in categories:
                category = encoder.encode(raw_category)
                # categories can be prefixed with one of (+@, +, -@, -)
                if category.startswith(b"+@"):
                    pieces.append(category)
                elif category.startswith(b"+"):
                    pieces.append(b"+@%s" % category[1:])
                elif category.startswith(b"-@"):
                    pieces.append(category)
                elif category.startswith(b"-"):
                    pieces.append(b"-@%s" % category[1:])
                else:
                    raise DataError(
                        f'Category "{encoder.decode(category, force=True)}" must be ' 'prefixed with "+" or "-"'
                    )
        if commands:
            for raw_cmd in commands:
                cmd = encoder.encode(raw_cmd)
                if not cmd.startswith(b"+") and not cmd.startswith(b"-"):
                    raise DataError(f'Command "{encoder.decode(cmd, force=True)}" must be ' 'prefixed with "+" or "-"')
                pieces.append(cmd)

        if keys:
            for raw_key in keys:
                key = encoder.encode(raw_key)
                pieces.append(b"~%s" % key)

        return self.execute_command("ACL SETUSER", *pieces)

    def acl_users(self) -> Awaitable:
        """处理acl用户相关逻辑。"""
        return self.execute_command("ACL USERS")

    def acl_whoami(self) -> Awaitable:
        """处理aclwhoami相关逻辑。"""
        return self.execute_command("ACL WHOAMI")

    def bgrewriteaof(self) -> Awaitable:
        """处理bgrewriteaof相关逻辑。"""
        return self.execute_command("BGREWRITEAOF")

    def bgsave(self) -> Awaitable:
        """
        Tell the Redis server to save its data to disk.  Unlike save(),
        this method is asynchronous and returns immediately.
        """
        return self.execute_command("BGSAVE")

    def client_kill(self, address: str) -> Awaitable:
        """处理clientkill相关逻辑。

        参数:
            address (str): address。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("CLIENT KILL", address)

    def client_kill_filter(
        self,
        _id: Optional[str] = None,
        _type: Optional[str] = None,
        addr: Optional[str] = None,
        skipme: Optional[bool] = None,
    ) -> Awaitable:
        """Disconnects client(s) using a variety of filter options

        参数:
            _id (Optional[str]): 标识。
            _type (Optional[str]): type。
            addr (Optional[str]): addr。
            skipme (Optional[bool]): skipme。

        返回:
            Awaitable: 返回处理结果。
        """
        args: List[Union[bytes, str]] = []
        if _type is not None:
            client_types = ("normal", "master", "slave", "pubsub")
            if str(_type).lower() not in client_types:
                raise DataError(f"CLIENT KILL type must be one of {client_types!r}")
            args.extend((b"TYPE", _type))
        if skipme is not None:
            if not isinstance(skipme, bool):
                raise DataError("CLIENT KILL skipme must be a bool")
            if skipme:
                args.extend((b"SKIPME", b"YES"))
            else:
                args.extend((b"SKIPME", b"NO"))
        if _id is not None:
            args.extend((b"ID", _id))
        if addr is not None:
            args.extend((b"ADDR", addr))
        if not args:
            raise DataError("CLIENT KILL <filter> <value> ... ... <filter> " "<value> must specify at least one filter")
        return self.execute_command("CLIENT KILL", *args)

    def client_list(self, _type: Optional[str] = None) -> Awaitable:
        """Returns a list of currently connected clients.

        参数:
            _type (Optional[str]): type。

        返回:
            Awaitable: 返回处理结果。
        """
        "Returns a list of currently connected clients"
        if _type is not None:
            client_types = ("normal", "master", "replica", "pubsub")
            if str(_type).lower() not in client_types:
                raise DataError(f"CLIENT LIST _type must be one of {client_types!r}")
            return self.execute_command("CLIENT LIST", b"TYPE", _type)
        return self.execute_command("CLIENT LIST")

    def client_getname(self) -> Awaitable:
        """处理clientgetname相关逻辑。"""
        return self.execute_command("CLIENT GETNAME")

    def client_id(self) -> Awaitable:
        """处理clientid相关逻辑。"""
        return self.execute_command("CLIENT ID")

    def client_setname(self, name: str) -> Awaitable:
        """处理clientsetname相关逻辑。

        参数:
            name (str): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("CLIENT SETNAME", name)

    def client_unblock(self, client_id: int, error: bool = False) -> Awaitable:
        """Unblocks a connection by its client id.

        参数:
            client_id (int): client标识。
            error (bool): error。

        返回:
            Awaitable: 返回处理结果。
        """
        args = ["CLIENT UNBLOCK", int(client_id)]
        if error:
            args.append(b"ERROR")
        return self.execute_command(*args)

    def client_pause(self, timeout: int) -> Awaitable:
        """Suspend all the Redis clients for the specified amount of time

        参数:
            timeout (int): timeout。

        返回:
            Awaitable: 返回处理结果。
        """
        if not isinstance(timeout, int):
            raise DataError("CLIENT PAUSE timeout must be an integer")
        return self.execute_command("CLIENT PAUSE", str(timeout))

    def readwrite(self) -> Awaitable:
        """处理readwrite相关逻辑。"""
        return self.execute_command("READWRITE")

    def readonly(self) -> Awaitable:
        """处理readonly相关逻辑。"""
        return self.execute_command("READONLY")

    def config_get(self, pattern: str = "*") -> Awaitable:
        """处理configget相关逻辑。

        参数:
            pattern (str): pattern。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("CONFIG GET", pattern)

    def config_set(self, name: str, value: EncodableT) -> Awaitable:
        """处理configset相关逻辑。

        参数:
            name (str): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("CONFIG SET", name, value)

    def config_resetstat(self) -> Awaitable:
        """处理configresetstat相关逻辑。"""
        return self.execute_command("CONFIG RESETSTAT")

    def config_rewrite(self) -> Awaitable:
        """处理configrewrite相关逻辑。"""
        return self.execute_command("CONFIG REWRITE")

    def dbsize(self) -> Awaitable:
        """处理dbsize相关逻辑。"""
        return self.execute_command("DBSIZE")

    def debug_object(self, key: KeyT) -> Awaitable:
        """处理debugobject相关逻辑。

        参数:
            key (KeyT): key。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("DEBUG OBJECT", key)

    def echo(self, value: EncodableT) -> Awaitable:
        """处理echo相关逻辑。

        参数:
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ECHO", value)

    def flushall(self, asynchronous: bool = False) -> Awaitable:
        """Delete all keys in all databases on the current host.

        参数:
            asynchronous (bool): asynchronous。

        返回:
            Awaitable: 返回处理结果。
        """
        args = []
        if asynchronous:
            args.append(b"ASYNC")
        return self.execute_command("FLUSHALL", *args)

    def flushdb(self, asynchronous: bool = False) -> Awaitable:
        """Delete all keys in the current database.

        参数:
            asynchronous (bool): asynchronous。

        返回:
            Awaitable: 返回处理结果。
        """
        args = []
        if asynchronous:
            args.append(b"ASYNC")
        return self.execute_command("FLUSHDB", *args)

    def swapdb(self, first: int, second: int) -> Awaitable:
        """处理swapdb相关逻辑。

        参数:
            first (int): first。
            second (int): second。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SWAPDB", first, second)

    def info(self, section: Optional[str] = None) -> Awaitable:
        """Returns a dictionary containing information about the Redis server

        参数:
            section (Optional[str]): section。

        返回:
            Awaitable: 返回处理结果。
        """
        if section is None:
            return self.execute_command("INFO")
        else:
            return self.execute_command("INFO", section)

    def lastsave(self) -> Awaitable:
        """
        Return a Python datetime object representing the last time the
        Redis database was saved to disk
        """
        return self.execute_command("LASTSAVE")

    def migrate(
        self,
        host: str,
        port: int,
        keys: KeysT,
        destination_db: int,
        timeout: int,
        copy: bool = False,
        replace: bool = False,
        auth: Optional[str] = None,
    ) -> Awaitable:
        """Migrate 1 or more keys from the current Redis server to a different

        参数:
            host (str): host。
            port (int): port。
            keys (KeysT): keys。
            destination_db (int): destinationdb。
            timeout (int): timeout。
            copy (bool): copy。
            replace (bool): replace。
            auth (Optional[str]): auth。

        返回:
            Awaitable: 返回处理结果。
        """
        keys = list_or_args(keys, [])
        if not keys:
            raise DataError("MIGRATE requires at least one key")
        pieces: List[EncodableT] = []
        if copy:
            pieces.append(b"COPY")
        if replace:
            pieces.append(b"REPLACE")
        if auth:
            pieces.append(b"AUTH")
            pieces.append(auth)
        pieces.append(b"KEYS")
        pieces.extend(keys)
        return self.execute_command("MIGRATE", host, port, "", destination_db, timeout, *pieces)

    def object(self, infotype: str, key: KeyT) -> Awaitable:
        """处理object相关逻辑。

        参数:
            infotype (str): infotype。
            key (KeyT): key。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("OBJECT", infotype, key, infotype=infotype)

    def memory_stats(self) -> Awaitable:
        """处理memorystats相关逻辑。"""
        return self.execute_command("MEMORY STATS")

    def memory_usage(self, key: KeyT, samples: Optional[int] = None) -> Awaitable:
        """Return the total memory usage for key, its value and associated

        参数:
            key (KeyT): key。
            samples (Optional[int]): samples。

        返回:
            Awaitable: 返回处理结果。
        """
        args = []
        if isinstance(samples, int):
            args.extend([b"SAMPLES", samples])
        return self.execute_command("MEMORY USAGE", key, *args)

    def memory_purge(self) -> Awaitable:
        """处理memorypurge相关逻辑。"""
        return self.execute_command("MEMORY PURGE")

    def ping(self) -> Awaitable:
        """处理ping相关逻辑。"""
        return self.execute_command("PING")

    def save(self) -> Awaitable:
        """
        Tell the Redis server to save its data to disk,
        blocking until the save is complete
        """
        return self.execute_command("SAVE")

    def sentinel_get_master_addr_by_name(self, service_name: str) -> Awaitable:
        """处理sentinelgetmasteraddrname相关逻辑。

        参数:
            service_name (str): service名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SENTINEL GET-MASTER-ADDR-BY-NAME", service_name)

    def sentinel_master(self, service_name: str) -> Awaitable:
        """处理sentinelmaster相关逻辑。

        参数:
            service_name (str): service名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SENTINEL MASTER", service_name)

    def sentinel_masters(self) -> Awaitable:
        """处理sentinelmasters相关逻辑。"""
        return self.execute_command("SENTINEL MASTERS")

    def sentinel_monitor(self, name: str, ip: str, port: int, quorum: int) -> Awaitable:
        """处理sentinelmonitor相关逻辑。

        参数:
            name (str): 名称。
            ip (str): ip。
            port (int): port。
            quorum (int): quorum。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SENTINEL MONITOR", name, ip, port, quorum)

    def sentinel_remove(self, name: str) -> Awaitable:
        """处理sentinelremove相关逻辑。

        参数:
            name (str): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SENTINEL REMOVE", name)

    def sentinel_sentinels(self, service_name: str) -> Awaitable:
        """处理sentinelsentinels相关逻辑。

        参数:
            service_name (str): service名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SENTINEL SENTINELS", service_name)

    def sentinel_set(self, name: str, option: str, value: EncodableT) -> Awaitable:
        """处理sentinelset相关逻辑。

        参数:
            name (str): 名称。
            option (str): option。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SENTINEL SET", name, option, value)

    def sentinel_slaves(self, service_name: str) -> Awaitable:
        """处理sentinelslaves相关逻辑。

        参数:
            service_name (str): service名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SENTINEL SLAVES", service_name)

    def shutdown(self, save: bool = False, nosave: bool = False) -> None:
        """Shutdown the Redis server.  If Redis has persistence configured,

        参数:
            save (bool): 保存。
            nosave (bool): nosave。
        """
        if save and nosave:
            raise DataError("SHUTDOWN save and nosave cannot both be set")
        args = ["SHUTDOWN"]
        if save:
            args.append("SAVE")
        if nosave:
            args.append("NOSAVE")
        try:
            self.execute_command(*args)
        except ConnectionError:
            # a ConnectionError here is expected
            return
        raise RedisError("SHUTDOWN seems to have failed.")

    def slaveof(self, host: Optional[str] = None, port: Optional[int] = None) -> Awaitable:
        """Set the server to be a replicated slave of the instance identified

        参数:
            host (Optional[str]): host。
            port (Optional[int]): port。

        返回:
            Awaitable: 返回处理结果。
        """
        if host is None and port is None:
            return self.execute_command("SLAVEOF", b"NO", b"ONE")
        return self.execute_command("SLAVEOF", host, port)

    def slowlog_get(self, num: Optional[int] = None) -> Awaitable:
        """Get the entries from the slowlog. If ``num`` is specified, get the

        参数:
            num (Optional[int]): num。

        返回:
            Awaitable: 返回处理结果。
        """
        args: List[EncodableT] = ["SLOWLOG GET"]
        if num is not None:
            args.append(num)
        decode_responses = self.connection_pool.connection_kwargs.get("decode_responses", False)
        return self.execute_command(*args, decode_responses=decode_responses)

    def slowlog_len(self) -> Awaitable:
        """处理slowloglen相关逻辑。"""
        return self.execute_command("SLOWLOG LEN")

    def slowlog_reset(self) -> Awaitable:
        """处理slowlog重置相关逻辑。"""
        return self.execute_command("SLOWLOG RESET")

    def time(self) -> Awaitable:
        """
        Returns the server time as a 2-item tuple of ints:
        (seconds since epoch, microseconds into this second).
        """
        return self.execute_command("TIME")

    def wait(self, num_replicas: int, timeout: int) -> Awaitable:
        """Redis synchronous replication

        参数:
            num_replicas (int): numreplicas。
            timeout (int): timeout。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("WAIT", num_replicas, timeout)

    # BASIC KEY COMMANDS
    def append(self, key: KeyT, value: EncodableT) -> Awaitable:
        """Appends the string ``value`` to the value at ``key``. If ``key``

        参数:
            key (KeyT): key。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("APPEND", key, value)

    def bitcount(self, key: KeyT, start: Optional[int] = None, end: Optional[int] = None) -> Awaitable:
        """Returns the count of set bits in the value of ``key``.  Optional

        参数:
            key (KeyT): key。
            start (Optional[int]): start。
            end (Optional[int]): end。

        返回:
            Awaitable: 返回处理结果。
        """
        params: List[EncodableT] = [key]
        if start is not None and end is not None:
            params.append(start)
            params.append(end)
        elif (start is not None and end is None) or (end is not None and start is None):
            raise DataError("Both start and end must be specified")
        return self.execute_command("BITCOUNT", *params)

    def bitfield(self, key: KeyT, default_overflow: Optional[str] = None) -> "BitFieldOperation":
        """Return a BitFieldOperation instance to conveniently construct one or

        参数:
            key (KeyT): key。
            default_overflow (Optional[str]): defaultoverflow。

        返回:
            'BitFieldOperation': 返回处理结果。
        """
        return BitFieldOperation(self, key, default_overflow=default_overflow)

    def bitop(self, operation: str, dest: KeyT, *keys: KeyT) -> Awaitable:
        """Perform a bitwise operation using ``operation`` between ``keys`` and

        参数:
            operation (str): operation。
            dest (KeyT): dest。
            keys (*KeyT): keys。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("BITOP", operation, dest, *keys)

    def bitpos(
        self,
        key: KeyT,
        bit: int,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> Awaitable:
        """Return the position of the first bit set to 1 or 0 in a string.

        参数:
            key (KeyT): key。
            bit (int): bit。
            start (Optional[int]): start。
            end (Optional[int]): end。

        返回:
            Awaitable: 返回处理结果。
        """
        if bit not in (0, 1):
            raise DataError("bit must be 0 or 1")
        params = [key, bit]

        if start is not None:
            params.append(start)
            if end is not None:
                params.append(end)
        elif end is not None:
            raise DataError("start argument is not set, when end is specified")
        return self.execute_command("BITPOS", *params)

    def decr(self, name: KeyT, amount: int = 1) -> Awaitable:
        """Decrements the value of ``key`` by ``amount``.  If no key exists,

        参数:
            name (KeyT): 名称。
            amount (int): amount。

        返回:
            Awaitable: 返回处理结果。
        """
        # An alias for ``decr()``, because it is already implemented
        # as DECRBY redis command.
        return self.decrby(name, amount)

    def decrby(self, name: KeyT, amount: int = 1) -> Awaitable:
        """Decrements the value of ``key`` by ``amount``.  If no key exists,

        参数:
            name (KeyT): 名称。
            amount (int): amount。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("DECRBY", name, amount)

    def delete(self, *names: KeyT) -> Awaitable:
        """处理delete相关逻辑。

        参数:
            names (*KeyT): names。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("DEL", *names)

    def dump(self, name: KeyT) -> Awaitable:
        """Return a serialized version of the value stored at the specified key.

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("DUMP", name)

    def exists(self, *names: KeyT) -> Awaitable:
        """处理存在相关逻辑。

        参数:
            names (*KeyT): names。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("EXISTS", *names)

    def expire(self, name: KeyT, time: ExpiryT) -> Awaitable:
        """Set an expire flag on key ``name`` for ``time`` seconds. ``time``

        参数:
            name (KeyT): 名称。
            time (ExpiryT): 时间。

        返回:
            Awaitable: 返回处理结果。
        """
        if isinstance(time, datetime.timedelta):
            time = int(time.total_seconds())
        return self.execute_command("EXPIRE", name, time)

    def expireat(self, name: KeyT, when: AbsExpiryT) -> Awaitable:
        """Set an expire flag on key ``name``. ``when`` can be represented

        参数:
            name (KeyT): 名称。
            when (AbsExpiryT): when。

        返回:
            Awaitable: 返回处理结果。
        """
        if isinstance(when, datetime.datetime):
            when = int(mod_time.mktime(when.timetuple()))
        return self.execute_command("EXPIREAT", name, when)

    def get(self, name: KeyT) -> Awaitable:
        """处理get相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("GET", name)

    def getbit(self, name: KeyT, offset: int) -> Awaitable:
        """处理getbit相关逻辑。

        参数:
            name (KeyT): 名称。
            offset (int): offset。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("GETBIT", name, offset)

    def getrange(self, key: KeyT, start: int, end: int) -> Awaitable:
        """Returns the substring of the string value stored at ``key``,

        参数:
            key (KeyT): key。
            start (int): start。
            end (int): end。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("GETRANGE", key, start, end)

    def getset(self, name: KeyT, value: EncodableT) -> Awaitable:
        """Sets the value at key ``name`` to ``value``

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("GETSET", name, value)

    def incr(self, name: KeyT, amount: int = 1) -> Awaitable:
        """Increments the value of ``key`` by ``amount``.  If no key exists,

        参数:
            name (KeyT): 名称。
            amount (int): amount。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.incrby(name, amount)

    def incrby(self, name: KeyT, amount: int = 1) -> Awaitable:
        """Increments the value of ``key`` by ``amount``.  If no key exists,

        参数:
            name (KeyT): 名称。
            amount (int): amount。

        返回:
            Awaitable: 返回处理结果。
        """
        # An alias for ``incr()``, because it is already implemented
        # as INCRBY redis command.
        return self.execute_command("INCRBY", name, amount)

    def incrbyfloat(self, name: KeyT, amount: float = 1.0) -> Awaitable:
        """Increments the value at key ``name`` by floating ``amount``.

        参数:
            name (KeyT): 名称。
            amount (float): amount。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("INCRBYFLOAT", name, amount)

    def keys(self, pattern: PatternT = "*") -> Awaitable:
        """处理keys相关逻辑。

        参数:
            pattern (PatternT): pattern。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("KEYS", pattern)

    def mget(self, keys: KeysT, *args: EncodableT) -> Awaitable:
        """处理mget相关逻辑。

        参数:
            keys (KeysT): keys。
            args (*EncodableT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        encoded_args = list_or_args(keys, args)
        options: Dict[str, Union[EncodableT, Iterable[EncodableT]]] = {}
        if not encoded_参数:
            options[EMPTY_RESPONSE] = []
        return self.execute_command("MGET", *encoded_args, **options)

    def mset(self, mapping: Mapping[AnyKeyT, EncodableT]) -> Awaitable:
        """Sets key/values based on a mapping. Mapping is a dictionary of

        参数:
            mapping (Mapping[AnyKeyT, EncodableT]): mapping。

        返回:
            Awaitable: 返回处理结果。
        """
        items: List[EncodableT] = []
        for pair in mapping.items():
            items.extend(pair)
        return self.execute_command("MSET", *items)

    def msetnx(self, mapping: Mapping[AnyKeyT, EncodableT]) -> Awaitable:
        """Sets key/values based on a mapping if none of the keys are already set.

        参数:
            mapping (Mapping[AnyKeyT, EncodableT]): mapping。

        返回:
            Awaitable: 返回处理结果。
        """
        items: List[EncodableT] = []
        for pair in mapping.items():
            items.extend(pair)
        return self.execute_command("MSETNX", *items)

    def move(self, name: KeyT, db: int) -> Awaitable:
        """处理move相关逻辑。

        参数:
            name (KeyT): 名称。
            db (int): db。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("MOVE", name, db)

    def persist(self, name: KeyT) -> Awaitable:
        """处理persist相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("PERSIST", name)

    def pexpire(self, name: KeyT, time: ExpiryT) -> Awaitable:
        """Set an expire flag on key ``name`` for ``time`` milliseconds.

        参数:
            name (KeyT): 名称。
            time (ExpiryT): 时间。

        返回:
            Awaitable: 返回处理结果。
        """
        if isinstance(time, datetime.timedelta):
            time = int(time.total_seconds() * 1000)
        return self.execute_command("PEXPIRE", name, time)

    def pexpireat(self, name: KeyT, when: AbsExpiryT) -> Awaitable:
        """Set an expire flag on key ``name``. ``when`` can be represented

        参数:
            name (KeyT): 名称。
            when (AbsExpiryT): when。

        返回:
            Awaitable: 返回处理结果。
        """
        if isinstance(when, datetime.datetime):
            ms = int(when.microsecond / 1000)
            when = int(mod_time.mktime(when.timetuple())) * 1000 + ms
        return self.execute_command("PEXPIREAT", name, when)

    def psetex(self, name: KeyT, time_ms: ExpiryT, value: EncodableT) -> Awaitable:
        """Set the value of key ``name`` to ``value`` that expires in ``time_ms``

        参数:
            name (KeyT): 名称。
            time_ms (ExpiryT): 时间ms。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        if isinstance(time_ms, datetime.timedelta):
            time_ms = int(time_ms.total_seconds() * 1000)
        return self.execute_command("PSETEX", name, time_ms, value)

    def pttl(self, name: KeyT) -> Awaitable:
        """处理pttl相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("PTTL", name)

    def randomkey(self) -> Awaitable:
        """处理randomkey相关逻辑。"""
        return self.execute_command("RANDOMKEY")

    def rename(self, src: KeyT, dst: KeyT) -> Awaitable:
        """处理rename相关逻辑。

        参数:
            src (KeyT): src。
            dst (KeyT): dst。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("RENAME", src, dst)

    def renamenx(self, src: KeyT, dst: KeyT) -> Awaitable:
        """处理renamenx相关逻辑。

        参数:
            src (KeyT): src。
            dst (KeyT): dst。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("RENAMENX", src, dst)

    def restore(
        self,
        name: KeyT,
        ttl: float,
        value: EncodableT,
        replace: bool = False,
        absttl: bool = False,
    ) -> Awaitable:
        """Create a key using the provided serialized value, previously obtained

        参数:
            name (KeyT): 名称。
            ttl (float): ttl。
            value (EncodableT): 输入值。
            replace (bool): replace。
            absttl (bool): absttl。

        返回:
            Awaitable: 返回处理结果。
        """
        params = [name, ttl, value]
        if replace:
            params.append("REPLACE")
        if absttl:
            params.append("ABSTTL")
        return self.execute_command("RESTORE", *params)

    def set(
        self,
        name: KeyT,
        value: EncodableT,
        ex: Optional[ExpiryT] = None,
        px: Optional[ExpiryT] = None,
        nx: bool = False,
        xx: bool = False,
        keepttl: bool = False,
    ) -> Awaitable:
        """Set the value at key ``name`` to ``value``

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。
            ex (Optional[ExpiryT]): ex。
            px (Optional[ExpiryT]): px。
            nx (bool): nx。
            xx (bool): xx。
            keepttl (bool): keepttl。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [name, value]
        if ex is not None:
            pieces.append("EX")
            if isinstance(ex, datetime.timedelta):
                ex = int(ex.total_seconds())
            pieces.append(ex)
        if px is not None:
            pieces.append("PX")
            if isinstance(px, datetime.timedelta):
                px = int(px.total_seconds() * 1000)
            pieces.append(px)

        if nx:
            pieces.append("NX")
        if xx:
            pieces.append("XX")

        if keepttl:
            pieces.append("KEEPTTL")

        return self.execute_command("SET", *pieces)

    def setbit(self, name: KeyT, offset: int, value: int) -> Awaitable:
        """Flag the ``offset`` in ``name`` as ``value``. Returns a boolean

        参数:
            name (KeyT): 名称。
            offset (int): offset。
            value (int): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        value = value and 1 or 0
        return self.execute_command("SETBIT", name, offset, value)

    def setex(self, name: KeyT, time: Union[int, datetime.timedelta], value: EncodableT) -> Awaitable:
        """Set the value of key ``name`` to ``value`` that expires in ``time``

        参数:
            name (KeyT): 名称。
            time (Union[int, datetime.timedelta]): 时间。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        if isinstance(time, datetime.timedelta):
            time = int(time.total_seconds())
        return self.execute_command("SETEX", name, time, value)

    def setnx(self, name: KeyT, value: EncodableT) -> Awaitable:
        """处理setnx相关逻辑。

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SETNX", name, value)

    def setrange(self, name: KeyT, offset: int, value: EncodableT) -> Awaitable:
        """Overwrite bytes in the value of ``name`` starting at ``offset`` with

        参数:
            name (KeyT): 名称。
            offset (int): offset。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SETRANGE", name, offset, value)

    def strlen(self, name: KeyT) -> Awaitable:
        """处理strlen相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("STRLEN", name)

    def substr(self, name: KeyT, start: int, end: int = -1) -> Awaitable:
        """Return a substring of the string at key ``name``. ``start`` and ``end``

        参数:
            name (KeyT): 名称。
            start (int): start。
            end (int): end。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SUBSTR", name, start, end)

    def touch(self, *args: KeyT) -> Awaitable:
        """Alters the last access time of a key(s) ``*args``. A key is ignored

        参数:
            args (*KeyT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("TOUCH", *args)

    def ttl(self, name: KeyT) -> Awaitable:
        """处理ttl相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("TTL", name)

    def type(self, name: KeyT) -> Awaitable:
        """处理type相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("TYPE", name)

    def unlink(self, *names: KeyT) -> Awaitable:
        """处理unlink相关逻辑。

        参数:
            names (*KeyT): names。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("UNLINK", *names)

    # LIST COMMANDS
    def blpop(self, keys: KeysT, timeout: TimeoutSecT = 0) -> Awaitable:
        """LPOP a value off of the first non-empty list

        参数:
            keys (KeysT): keys。
            timeout (TimeoutSecT): timeout。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("BLPOP", *list_or_args(keys, (timeout,)))

    def brpop(self, keys: KeysT, timeout: TimeoutSecT = 0) -> Awaitable:
        """RPOP a value off of the first non-empty list

        参数:
            keys (KeysT): keys。
            timeout (TimeoutSecT): timeout。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("BRPOP", *list_or_args(keys, (timeout,)))

    def brpoplpush(self, src: KeyT, dst: KeyT, timeout: TimeoutSecT = 0) -> Awaitable:
        """Pop a value off the tail of ``src``, push it on the head of ``dst``

        参数:
            src (KeyT): src。
            dst (KeyT): dst。
            timeout (TimeoutSecT): timeout。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("BRPOPLPUSH", src, dst, timeout)

    def lindex(self, name: KeyT, index: int) -> Awaitable:
        """Return the item from list ``name`` at position ``index``

        参数:
            name (KeyT): 名称。
            index (int): index。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LINDEX", name, index)

    def linsert(self, name: KeyT, where: str, refvalue: EncodableT, value: EncodableT) -> Awaitable:
        """Insert ``value`` in list ``name`` either immediately before or after

        参数:
            name (KeyT): 名称。
            where (str): where。
            refvalue (EncodableT): refvalue。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LINSERT", name, where, refvalue, value)

    def llen(self, name: KeyT) -> Awaitable:
        """处理llen相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LLEN", name)

    def lpop(self, name: KeyT) -> Awaitable:
        """处理lpop相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LPOP", name)

    def lpush(self, name: KeyT, *values: EncodableT) -> Awaitable:
        """处理lpush相关逻辑。

        参数:
            name (KeyT): 名称。
            values (*EncodableT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LPUSH", name, *values)

    def lpushx(self, name: KeyT, value: EncodableT) -> Awaitable:
        """处理lpushx相关逻辑。

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LPUSHX", name, value)

    def lrange(self, name: KeyT, start: int, end: int) -> Awaitable:
        """Return a slice of the list ``name`` between

        参数:
            name (KeyT): 名称。
            start (int): start。
            end (int): end。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LRANGE", name, start, end)

    def lrem(self, name: KeyT, count: int, value: EncodableT) -> Awaitable:
        """Remove the first ``count`` occurrences of elements equal to ``value``

        参数:
            name (KeyT): 名称。
            count (int): 统计。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LREM", name, count, value)

    def lset(self, name: KeyT, index: int, value: EncodableT) -> Awaitable:
        """处理lset相关逻辑。

        参数:
            name (KeyT): 名称。
            index (int): index。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LSET", name, index, value)

    def ltrim(self, name: KeyT, start: int, end: int) -> Awaitable:
        """Trim the list ``name``, removing all values not within the slice

        参数:
            name (KeyT): 名称。
            start (int): start。
            end (int): end。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("LTRIM", name, start, end)

    def rpop(self, name: KeyT) -> Awaitable:
        """处理rpop相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("RPOP", name)

    def rpoplpush(self, src: KeyT, dst: KeyT) -> Awaitable:
        """RPOP a value off of the ``src`` list and atomically LPUSH it

        参数:
            src (KeyT): src。
            dst (KeyT): dst。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("RPOPLPUSH", src, dst)

    def rpush(self, name: KeyT, *values: EncodableT) -> Awaitable:
        """处理rpush相关逻辑。

        参数:
            name (KeyT): 名称。
            values (*EncodableT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("RPUSH", name, *values)

    def rpushx(self, name: KeyT, value: EncodableT) -> Awaitable:
        """处理rpushx相关逻辑。

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("RPUSHX", name, value)

    def lpos(
        self,
        name: KeyT,
        value: EncodableT,
        rank: Optional[int] = None,
        count: Optional[int] = None,
        maxlen: Optional[int] = None,
    ) -> Awaitable:
        """Get position of ``value`` within the list ``name``

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。
            rank (Optional[int]): rank。
            count (Optional[int]): 统计。
            maxlen (Optional[int]): maxlen。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [name, value]
        if rank is not None:
            pieces.extend(["RANK", rank])

        if count is not None:
            pieces.extend(["COUNT", count])

        if maxlen is not None:
            pieces.extend(["MAXLEN", maxlen])

        return self.execute_command("LPOS", *pieces)

    def sort(
        self,
        name: KeyT,
        start: Optional[int] = None,
        num: Optional[int] = None,
        by: Optional[KeyT] = None,
        get: Optional[KeysT] = None,
        desc: bool = False,
        alpha: bool = False,
        store: Optional[KeyT] = None,
        groups: bool = False,
    ) -> Awaitable:
        """Sort and return the list, set or sorted set at ``name``.

        参数:
            name (KeyT): 名称。
            start (Optional[int]): start。
            num (Optional[int]): num。
            by (Optional[KeyT]): by。
            get (Optional[KeysT]): 获取。
            desc (bool): 描述信息。
            alpha (bool): alpha。
            store (Optional[KeyT]): store。
            groups (bool): 群组。

        返回:
            Awaitable: 返回处理结果。
        """
        if (start is not None and num is None) or (num is not None and start is None):
            raise DataError("``start`` and ``num`` must both be specified")

        pieces: List[EncodableT] = [name]
        if by is not None:
            pieces.append(b"BY")
            pieces.append(by)
        if start is not None and num is not None:
            pieces.append(b"LIMIT")
            pieces.append(start)
            pieces.append(num)
        if get is not None:
            # If get is a string assume we want to get a single value.
            # Otherwise assume it's an interable and we want to get multiple
            # values. We can't just iterate blindly because strings are
            # iterable.
            if isinstance(get, (bytes, str)):
                pieces.append(b"GET")
                pieces.append(get)
            else:
                for g in get:
                    pieces.append(b"GET")
                    pieces.append(g)
        if desc:
            pieces.append(b"DESC")
        if alpha:
            pieces.append(b"ALPHA")
        if store is not None:
            pieces.append(b"STORE")
            pieces.append(store)

        if groups:
            if not get or isinstance(get, (bytes, str)) or len(get) < 2:
                raise DataError(
                    'when using "groups" the "get" argument ' "must be specified and contain at least " "two keys"
                )
            options: Dict[str, Optional[int]] = {"groups": len(get)}
        else:
            options = {"groups": None}

        return self.execute_command("SORT", *pieces, **options)

    # SCAN COMMANDS
    def scan(
        self,
        cursor: int = 0,
        match: Optional[PatternT] = None,
        count: Optional[int] = None,
        _type: Optional[str] = None,
    ) -> Awaitable:
        """Incrementally return lists of key names. Also return a cursor

        参数:
            cursor (int): cursor。
            match (Optional[PatternT]): match。
            count (Optional[int]): 统计。
            _type (Optional[str]): type。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [cursor]
        if match is not None:
            pieces.extend([b"MATCH", match])
        if count is not None:
            pieces.extend([b"COUNT", count])
        if _type is not None:
            pieces.extend([b"TYPE", _type])
        return self.execute_command("SCAN", *pieces)

    async def scan_iter(
        self,
        match: Optional[PatternT] = None,
        count: Optional[int] = None,
        _type: Optional[str] = None,
    ) -> AsyncIterator:
        """Make an iterator using the SCAN command so that the client doesn't

        参数:
            match (Optional[PatternT]): match。
            count (Optional[int]): 统计。
            _type (Optional[str]): type。

        返回:
            AsyncIterator: 返回处理结果。
        """
        cursor = None
        while cursor != 0:
            cursor, data = await self.scan(cursor=cursor or 0, match=match, count=count, _type=_type)
            for d in data:
                yield d

    def sscan(
        self,
        name: KeyT,
        cursor: int = 0,
        match: Optional[PatternT] = None,
        count: Optional[int] = None,
    ) -> Awaitable:
        """Incrementally return lists of elements in a set. Also return a cursor

        参数:
            name (KeyT): 名称。
            cursor (int): cursor。
            match (Optional[PatternT]): match。
            count (Optional[int]): 统计。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [name, cursor]
        if match is not None:
            pieces.extend([b"MATCH", match])
        if count is not None:
            pieces.extend([b"COUNT", count])
        return self.execute_command("SSCAN", *pieces)

    async def sscan_iter(
        self, name: KeyT, match: Optional[PatternT] = None, count: Optional[int] = None
    ) -> AsyncIterator:
        """Make an iterator using the SSCAN command so that the client doesn't

        参数:
            name (KeyT): 名称。
            match (Optional[PatternT]): match。
            count (Optional[int]): 统计。

        返回:
            AsyncIterator: 返回处理结果。
        """
        cursor = None
        while cursor != 0:
            cursor, data = await self.sscan(name, cursor=cursor or 0, match=match, count=count)
            for d in data:
                yield d

    def hscan(
        self,
        name: KeyT,
        cursor: int = 0,
        match: Optional[PatternT] = None,
        count: Optional[int] = None,
    ) -> Awaitable:
        """Incrementally return key/value slices in a hash. Also return a cursor

        参数:
            name (KeyT): 名称。
            cursor (int): cursor。
            match (Optional[PatternT]): match。
            count (Optional[int]): 统计。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [name, cursor]
        if match is not None:
            pieces.extend([b"MATCH", match])
        if count is not None:
            pieces.extend([b"COUNT", count])
        return self.execute_command("HSCAN", *pieces)

    async def hscan_iter(
        self, name: str, match: Optional[PatternT] = None, count: Optional[int] = None
    ) -> AsyncIterator:
        """Make an iterator using the HSCAN command so that the client doesn't

        参数:
            name (str): 名称。
            match (Optional[PatternT]): match。
            count (Optional[int]): 统计。

        返回:
            AsyncIterator: 返回处理结果。
        """
        cursor = None
        while cursor != 0:
            cursor, data = await self.hscan(name, cursor=cursor or 0, match=match, count=count)
            for it in data.items():
                yield it

    def zscan(
        self,
        name: KeyT,
        cursor: int = 0,
        match: Optional[PatternT] = None,
        count: Optional[int] = None,
        score_cast_func: Union[Type, Callable] = float,
    ) -> Awaitable:
        """Incrementally return lists of elements in a sorted set. Also return a

        参数:
            name (KeyT): 名称。
            cursor (int): cursor。
            match (Optional[PatternT]): match。
            count (Optional[int]): 统计。
            score_cast_func (Union[Type, Callable]): scorecastfunc。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [name, cursor]
        if match is not None:
            pieces.extend([b"MATCH", match])
        if count is not None:
            pieces.extend([b"COUNT", count])
        options = {"score_cast_func": score_cast_func}
        return self.execute_command("ZSCAN", *pieces, **options)

    async def zscan_iter(
        self,
        name: KeyT,
        match: Optional[PatternT] = None,
        count: Optional[int] = None,
        score_cast_func: Union[Type, Callable] = float,
    ) -> AsyncIterator:
        """Make an iterator using the ZSCAN command so that the client doesn't

        参数:
            name (KeyT): 名称。
            match (Optional[PatternT]): match。
            count (Optional[int]): 统计。
            score_cast_func (Union[Type, Callable]): scorecastfunc。

        返回:
            AsyncIterator: 返回处理结果。
        """
        cursor = None
        while cursor != 0:
            cursor, data = await self.zscan(
                name,
                cursor=cursor or 0,
                match=match,
                count=count,
                score_cast_func=score_cast_func,
            )
            for d in data:
                yield d

    # SET COMMANDS
    def sadd(self, name: KeyT, *values: EncodableT) -> Awaitable:
        """处理sadd相关逻辑。

        参数:
            name (KeyT): 名称。
            values (*EncodableT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SADD", name, *values)

    def scard(self, name: KeyT) -> Awaitable:
        """处理scard相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SCARD", name)

    def sdiff(self, keys: KeysT, *args: EncodableT) -> Awaitable:
        """处理sdiff相关逻辑。

        参数:
            keys (KeysT): keys。
            args (*EncodableT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        parsed_args = list_or_args(keys, args)
        return self.execute_command("SDIFF", *parsed_args)

    def sdiffstore(self, dest: KeyT, keys: KeysT, *args: EncodableT) -> Awaitable:
        """Store the difference of sets specified by ``keys`` into a new

        参数:
            dest (KeyT): dest。
            keys (KeysT): keys。
            args (*EncodableT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        parsed_args = list_or_args(keys, args)
        return self.execute_command("SDIFFSTORE", dest, *parsed_args)

    def sinter(self, keys: KeysT, *args: EncodableT) -> Awaitable:
        """处理sinter相关逻辑。

        参数:
            keys (KeysT): keys。
            args (*EncodableT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        parsed_args = list_or_args(keys, args)
        return self.execute_command("SINTER", *parsed_args)

    def sinterstore(self, dest: KeyT, keys: KeysT, *args: EncodableT) -> Awaitable:
        """Store the intersection of sets specified by ``keys`` into a new

        参数:
            dest (KeyT): dest。
            keys (KeysT): keys。
            args (*EncodableT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        parsed_args = list_or_args(keys, args)
        return self.execute_command("SINTERSTORE", dest, *parsed_args)

    def sismember(self, name: KeyT, value: EncodableT) -> Awaitable:
        """处理sismember相关逻辑。

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SISMEMBER", name, value)

    def smembers(self, name: KeyT) -> Awaitable:
        """处理smembers相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SMEMBERS", name)

    def smove(self, src: KeyT, dst: KeyT, value: EncodableT) -> Awaitable:
        """处理smove相关逻辑。

        参数:
            src (KeyT): src。
            dst (KeyT): dst。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SMOVE", src, dst, value)

    def spop(self, name: KeyT, count: Optional[int] = None) -> Awaitable:
        """处理spop相关逻辑。

        参数:
            name (KeyT): 名称。
            count (Optional[int]): 统计。

        返回:
            Awaitable: 返回处理结果。
        """
        args = (count is not None) and [count] or []
        return self.execute_command("SPOP", name, *args)

    def srandmember(self, name: KeyT, number: Optional[int] = None) -> Awaitable:
        """If ``number`` is None, returns a random member of set ``name``.

        参数:
            name (KeyT): 名称。
            number (Optional[int]): number。

        返回:
            Awaitable: 返回处理结果。
        """
        args = (number is not None) and [number] or []
        return self.execute_command("SRANDMEMBER", name, *args)

    def srem(self, name: KeyT, *values: EncodableT) -> Awaitable:
        """处理srem相关逻辑。

        参数:
            name (KeyT): 名称。
            values (*EncodableT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SREM", name, *values)

    def sunion(self, keys: KeysT, *args: EncodableT) -> Awaitable:
        """处理sunion相关逻辑。

        参数:
            keys (KeysT): keys。
            args (*EncodableT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        parsed_args = list_or_args(keys, args)
        return self.execute_command("SUNION", *parsed_args)

    def sunionstore(self, dest: KeyT, keys: KeysT, *args: EncodableT) -> Awaitable:
        """Store the union of sets specified by ``keys`` into a new

        参数:
            dest (KeyT): dest。
            keys (KeysT): keys。
            args (*EncodableT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        parsed_args = list_or_args(keys, args)
        return self.execute_command("SUNIONSTORE", dest, *parsed_args)

    # STREAMS COMMANDS
    def xack(self, name: KeyT, groupname: GroupT, *ids: StreamIdT) -> Awaitable:
        """Acknowledges the successful processing of one or more messages.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。
            ids (*StreamIdT): 标识列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XACK", name, groupname, *ids)

    def xadd(
        self,
        name: KeyT,
        fields: Dict[FieldT, EncodableT],
        id: StreamIdT = "*",
        maxlen: Optional[int] = None,
        approximate: bool = True,
    ) -> Awaitable:
        """Add to a stream.

        参数:
            name (KeyT): 名称。
            fields (Dict[FieldT, EncodableT]): fields。
            id (StreamIdT): 标识。
            maxlen (Optional[int]): maxlen。
            approximate (bool): approximate。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = []
        if maxlen is not None:
            if not isinstance(maxlen, int) or maxlen < 1:
                raise DataError("XADD maxlen must be a positive integer")
            pieces.append(b"MAXLEN")
            if approximate:
                pieces.append(b"~")
            pieces.append(str(maxlen))
        pieces.append(id)
        if not isinstance(fields, dict) or len(fields) == 0:
            raise DataError("XADD fields must be a non-empty dict")
        for pair in fields.items():
            pieces.extend(pair)
        return self.execute_command("XADD", name, *pieces)

    def xclaim(
        self,
        name: KeyT,
        groupname: GroupT,
        consumername: ConsumerT,
        min_idle_time: int,
        message_ids: Union[List[StreamIdT], Tuple[StreamIdT]],
        idle: Optional[int] = None,
        time: Optional[int] = None,
        retrycount: Optional[int] = None,
        force: bool = False,
        justid: bool = False,
    ) -> Awaitable:
        """Changes the ownership of a pending message.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。
            consumername (ConsumerT): consumername。
            min_idle_time (int): minidle时间。
            message_ids (Union[List[StreamIdT], Tuple[StreamIdT]]): 消息标识列表。
            idle (Optional[int]): idle。
            time (Optional[int]): 时间。
            retrycount (Optional[int]): retrycount。
            force (bool): force。
            justid (bool): justid。

        返回:
            Awaitable: 返回处理结果。
        """
        if not isinstance(min_idle_time, int) or min_idle_time < 0:
            raise DataError("XCLAIM min_idle_time must be a non negative " "integer")
        if not isinstance(message_ids, (list, tuple)) or not message_ids:
            raise DataError("XCLAIM message_ids must be a non empty list or " "tuple of message IDs to claim")

        kwargs = {}
        pieces: List[EncodableT] = [name, groupname, consumername, str(min_idle_time)]
        pieces.extend(list(message_ids))

        if idle is not None:
            if not isinstance(idle, int):
                raise DataError("XCLAIM idle must be an integer")
            pieces.extend((b"IDLE", str(idle)))
        if time is not None:
            if not isinstance(time, int):
                raise DataError("XCLAIM time must be an integer")
            pieces.extend((b"TIME", str(time)))
        if retrycount is not None:
            if not isinstance(retrycount, int):
                raise DataError("XCLAIM retrycount must be an integer")
            pieces.extend((b"RETRYCOUNT", str(retrycount)))

        if force:
            if not isinstance(force, bool):
                raise DataError("XCLAIM force must be a boolean")
            pieces.append(b"FORCE")
        if justid:
            if not isinstance(justid, bool):
                raise DataError("XCLAIM justid must be a boolean")
            pieces.append(b"JUSTID")
            kwargs["parse_justid"] = True
        return self.execute_command("XCLAIM", *pieces, **kwargs)

    def xdel(self, name: KeyT, *ids: StreamIdT) -> Awaitable:
        """Deletes one or more messages from a stream.

        参数:
            name (KeyT): 名称。
            ids (*StreamIdT): 标识列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XDEL", name, *ids)

    def xgroup_create(self, name: KeyT, groupname: GroupT, id: StreamIdT = "$", mkstream: bool = False) -> Awaitable:
        """Create a new consumer group associated with a stream.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。
            id (StreamIdT): 标识。
            mkstream (bool): mkstream。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = ["XGROUP CREATE", name, groupname, id]
        if mkstream:
            pieces.append(b"MKSTREAM")
        return self.execute_command(*pieces)

    def xgroup_delconsumer(self, name: KeyT, groupname: GroupT, consumername: ConsumerT) -> Awaitable:
        """Remove a specific consumer from a consumer group.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。
            consumername (ConsumerT): consumername。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XGROUP DELCONSUMER", name, groupname, consumername)

    def xgroup_destroy(self, name: KeyT, groupname: GroupT) -> Awaitable:
        """Destroy a consumer group.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XGROUP DESTROY", name, groupname)

    def xgroup_setid(self, name: KeyT, groupname: GroupT, id: StreamIdT) -> Awaitable:
        """Set the consumer group last delivered ID to something else.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。
            id (StreamIdT): 标识。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XGROUP SETID", name, groupname, id)

    def xinfo_consumers(self, name: KeyT, groupname: GroupT) -> Awaitable:
        """Returns general information about the consumers in the group.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XINFO CONSUMERS", name, groupname)

    def xinfo_groups(self, name: KeyT) -> Awaitable:
        """Returns general information about the consumer groups of the stream.

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XINFO GROUPS", name)

    def xinfo_stream(self, name: KeyT) -> Awaitable:
        """Returns general information about the stream.

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XINFO STREAM", name)

    def xlen(self, name: KeyT) -> Awaitable:
        """处理xlen相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XLEN", name)

    def xpending(self, name: KeyT, groupname: GroupT) -> Awaitable:
        """Returns information about pending messages of a group.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("XPENDING", name, groupname)

    def xpending_range(
        self,
        name: KeyT,
        groupname: GroupT,
        min: Optional[StreamIdT],
        max: Optional[StreamIdT],
        count: Optional[int],
        consumername: Optional[ConsumerT] = None,
    ) -> Awaitable:
        """Returns information about pending messages, in a range.

        参数:
            name (KeyT): 名称。
            groupname (GroupT): groupname。
            min (Optional[StreamIdT]): min。
            max (Optional[StreamIdT]): max。
            count (Optional[int]): 统计。
            consumername (Optional[ConsumerT]): consumername。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [name, groupname]
        if min is not None or max is not None or count is not None:
            if min is None or max is None or count is None:
                raise DataError("XPENDING must be provided with min, max " "and count parameters, or none of them. ")
            if not isinstance(count, int) or count < -1:
                raise DataError("XPENDING count must be a integer >= -1")
            pieces.extend((min, max, str(count)))
        if consumername is not None:
            if min is None or max is None or count is None:
                raise DataError(
                    "if XPENDING is provided with consumername,"
                    " it must be provided with min, max and"
                    " count parameters"
                )
            pieces.append(consumername)
        return self.execute_command("XPENDING", *pieces, parse_detail=True)

    def xrange(
        self,
        name: KeyT,
        min: StreamIdT = "-",
        max: StreamIdT = "+",
        count: Optional[int] = None,
    ) -> Awaitable:
        """Read stream values within an interval.

        参数:
            name (KeyT): 名称。
            min (StreamIdT): min。
            max (StreamIdT): max。
            count (Optional[int]): 统计。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [min, max]
        if count is not None:
            if not isinstance(count, int) or count < 1:
                raise DataError("XRANGE count must be a positive integer")
            pieces.append(b"COUNT")
            pieces.append(str(count))

        return self.execute_command("XRANGE", name, *pieces)

    def xread(
        self,
        streams: Dict[KeyT, StreamIdT],
        count: Optional[int] = None,
        block: Optional[int] = None,
    ) -> Awaitable:
        """Block and monitor multiple streams for new data.

        参数:
            streams (Dict[KeyT, StreamIdT]): streams。
            count (Optional[int]): 统计。
            block (Optional[int]): block。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = []
        if block is not None:
            if not isinstance(block, int) or block < 0:
                raise DataError("XREAD block must be a non-negative integer")
            pieces.append(b"BLOCK")
            pieces.append(str(block))
        if count is not None:
            if not isinstance(count, int) or count < 1:
                raise DataError("XREAD count must be a positive integer")
            pieces.append(b"COUNT")
            pieces.append(str(count))
        if not isinstance(streams, dict) or len(streams) == 0:
            raise DataError("XREAD streams must be a non empty dict")
        pieces.append(b"STREAMS")
        keys, values = zip(*streams.items())
        pieces.extend(keys)
        pieces.extend(values)
        return self.execute_command("XREAD", *pieces)

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Dict[KeyT, StreamIdT],
        count: Optional[int] = None,
        block: Optional[int] = None,
        noack: bool = False,
    ) -> Awaitable:
        """Read from a stream via a consumer group.

        参数:
            groupname (str): groupname。
            consumername (str): consumername。
            streams (Dict[KeyT, StreamIdT]): streams。
            count (Optional[int]): 统计。
            block (Optional[int]): block。
            noack (bool): noack。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [b"GROUP", groupname, consumername]
        if count is not None:
            if not isinstance(count, int) or count < 1:
                raise DataError("XREADGROUP count must be a positive integer")
            pieces.append(b"COUNT")
            pieces.append(str(count))
        if block is not None:
            if not isinstance(block, int) or block < 0:
                raise DataError("XREADGROUP block must be a non-negative " "integer")
            pieces.append(b"BLOCK")
            pieces.append(str(block))
        if noack:
            pieces.append(b"NOACK")
        if not isinstance(streams, dict) or len(streams) == 0:
            raise DataError("XREADGROUP streams must be a non empty dict")
        pieces.append(b"STREAMS")
        pieces.extend(streams.keys())
        pieces.extend(streams.values())
        return self.execute_command("XREADGROUP", *pieces)

    def xrevrange(
        self,
        name: KeyT,
        max: StreamIdT = "+",
        min: StreamIdT = "-",
        count: Optional[int] = None,
    ) -> Awaitable:
        """Read stream values within an interval, in reverse order.

        参数:
            name (KeyT): 名称。
            max (StreamIdT): max。
            min (StreamIdT): min。
            count (Optional[int]): 统计。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [max, min]
        if count is not None:
            if not isinstance(count, int) or count < 1:
                raise DataError("XREVRANGE count must be a positive integer")
            pieces.append(b"COUNT")
            pieces.append(str(count))

        return self.execute_command("XREVRANGE", name, *pieces)

    def xtrim(self, name: KeyT, maxlen: int, approximate: bool = True) -> Awaitable:
        """Trims old messages from a stream.

        参数:
            name (KeyT): 名称。
            maxlen (int): maxlen。
            approximate (bool): approximate。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [b"MAXLEN"]
        if approximate:
            pieces.append(b"~")
        pieces.append(maxlen)
        return self.execute_command("XTRIM", name, *pieces)

    # SORTED SET COMMANDS
    def zadd(
        self,
        name: KeyT,
        mapping: Mapping[AnyKeyT, EncodableT],
        nx: bool = False,
        xx: bool = False,
        ch: bool = False,
        incr: bool = False,
    ) -> Awaitable:
        """Set any number of element-name, score pairs to the key ``name``. Pairs

        参数:
            name (KeyT): 名称。
            mapping (Mapping[AnyKeyT, EncodableT]): mapping。
            nx (bool): nx。
            xx (bool): xx。
            ch (bool): ch。
            incr (bool): incr。

        返回:
            Awaitable: 返回处理结果。
        """
        if not mapping:
            raise DataError("ZADD requires at least one element/score pair")
        if nx and xx:
            raise DataError("ZADD allows either 'nx' or 'xx', not both")
        if incr and len(mapping) != 1:
            raise DataError("ZADD option 'incr' only works when passing a " "single element/score pair")
        pieces: List[EncodableT] = []
        options = {}
        if nx:
            pieces.append(b"NX")
        if xx:
            pieces.append(b"XX")
        if ch:
            pieces.append(b"CH")
        if incr:
            pieces.append(b"INCR")
            options["as_score"] = True
        for pair in mapping.items():
            pieces.append(pair[1])
            pieces.append(pair[0])
        return self.execute_command("ZADD", name, *pieces, **options)

    def zcard(self, name: KeyT) -> Awaitable:
        """处理zcard相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZCARD", name)

    def zcount(self, name: KeyT, min: ZScoreBoundT, max: ZScoreBoundT) -> Awaitable:
        """Returns the number of elements in the sorted set at key ``name`` with

        参数:
            name (KeyT): 名称。
            min (ZScoreBoundT): min。
            max (ZScoreBoundT): max。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZCOUNT", name, min, max)

    def zincrby(self, name: KeyT, amount: float, value: EncodableT) -> Awaitable:
        """处理zincrby相关逻辑。

        参数:
            name (KeyT): 名称。
            amount (float): amount。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZINCRBY", name, amount, value)

    def zinterstore(
        self,
        dest: KeyT,
        keys: Union[Sequence[KeyT], Mapping[AnyKeyT, float]],
        aggregate: Optional[str] = None,
    ) -> Awaitable:
        """Intersect multiple sorted sets specified by ``keys`` into

        参数:
            dest (KeyT): dest。
            keys (Union[Sequence[KeyT], Mapping[AnyKeyT, float]]): keys。
            aggregate (Optional[str]): aggregate。

        返回:
            Awaitable: 返回处理结果。
        """
        return self._zaggregate("ZINTERSTORE", dest, keys, aggregate)

    def zlexcount(self, name: KeyT, min: EncodableT, max: EncodableT) -> Awaitable:
        """Return the number of items in the sorted set ``name`` between the

        参数:
            name (KeyT): 名称。
            min (EncodableT): min。
            max (EncodableT): max。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZLEXCOUNT", name, min, max)

    def zpopmax(self, name: KeyT, count: Optional[int] = None) -> Awaitable:
        """Remove and return up to ``count`` members with the highest scores

        参数:
            name (KeyT): 名称。
            count (Optional[int]): 统计。

        返回:
            Awaitable: 返回处理结果。
        """
        args = (count is not None) and [count] or []
        options = {"withscores": True}
        return self.execute_command("ZPOPMAX", name, *args, **options)

    def zpopmin(self, name: KeyT, count: Optional[int] = None) -> Awaitable:
        """Remove and return up to ``count`` members with the lowest scores

        参数:
            name (KeyT): 名称。
            count (Optional[int]): 统计。

        返回:
            Awaitable: 返回处理结果。
        """
        args = (count is not None) and [count] or []
        options = {"withscores": True}
        return self.execute_command("ZPOPMIN", name, *args, **options)

    def bzpopmax(self, keys: KeysT, timeout: TimeoutSecT = 0) -> Awaitable:
        """ZPOPMAX a value off of the first non-empty sorted set

        参数:
            keys (KeysT): keys。
            timeout (TimeoutSecT): timeout。

        返回:
            Awaitable: 返回处理结果。
        """
        parsed_keys = list_or_args(keys, (timeout,))
        return self.execute_command("BZPOPMAX", *parsed_keys)

    def bzpopmin(self, keys: KeysT, timeout: TimeoutSecT = 0) -> Awaitable:
        """ZPOPMIN a value off of the first non-empty sorted set

        参数:
            keys (KeysT): keys。
            timeout (TimeoutSecT): timeout。

        返回:
            Awaitable: 返回处理结果。
        """
        klist: List[EncodableT] = list_or_args(keys, None)
        klist.append(timeout)
        return self.execute_command("BZPOPMIN", *klist)

    def zrange(
        self,
        name: KeyT,
        start: int,
        end: int,
        desc: bool = False,
        withscores: bool = False,
        score_cast_func: Union[Type, Callable] = float,
    ) -> Awaitable:
        """Return a range of values from sorted set ``name`` between

        参数:
            name (KeyT): 名称。
            start (int): start。
            end (int): end。
            desc (bool): 描述信息。
            withscores (bool): withscores。
            score_cast_func (Union[Type, Callable]): scorecastfunc。

        返回:
            Awaitable: 返回处理结果。
        """
        if desc:
            return self.zrevrange(name, start, end, withscores, score_cast_func)
        pieces: List[EncodableT] = ["ZRANGE", name, start, end]
        if withscores:
            pieces.append(b"WITHSCORES")
        options = {"withscores": withscores, "score_cast_func": score_cast_func}
        return self.execute_command(*pieces, **options)

    def zrangebylex(
        self,
        name: KeyT,
        min: EncodableT,
        max: EncodableT,
        start: Optional[int] = None,
        num: Optional[int] = None,
    ) -> Awaitable:
        """Return the lexicographical range of values from sorted set ``name``

        参数:
            name (KeyT): 名称。
            min (EncodableT): min。
            max (EncodableT): max。
            start (Optional[int]): start。
            num (Optional[int]): num。

        返回:
            Awaitable: 返回处理结果。
        """
        if (start is not None and num is None) or (num is not None and start is None):
            raise DataError("``start`` and ``num`` must both be specified")
        pieces: List[EncodableT] = ["ZRANGEBYLEX", name, min, max]
        if start is not None and num is not None:
            pieces.extend([b"LIMIT", start, num])
        return self.execute_command(*pieces)

    def zrevrangebylex(
        self,
        name: KeyT,
        max: EncodableT,
        min: EncodableT,
        start: Optional[int] = None,
        num: Optional[int] = None,
    ) -> Awaitable:
        """Return the reversed lexicographical range of values from sorted set

        参数:
            name (KeyT): 名称。
            max (EncodableT): max。
            min (EncodableT): min。
            start (Optional[int]): start。
            num (Optional[int]): num。

        返回:
            Awaitable: 返回处理结果。
        """
        if (start is not None and num is None) or (num is not None and start is None):
            raise DataError("``start`` and ``num`` must both be specified")
        pieces: List[EncodableT] = ["ZREVRANGEBYLEX", name, max, min]
        if start is not None and num is not None:
            pieces.extend([b"LIMIT", start, num])
        return self.execute_command(*pieces)

    def zrangebyscore(
        self,
        name: KeyT,
        min: ZScoreBoundT,
        max: ZScoreBoundT,
        start: Optional[int] = None,
        num: Optional[int] = None,
        withscores: bool = False,
        score_cast_func: Union[Type, Callable] = float,
    ) -> Awaitable:
        """Return a range of values from the sorted set ``name`` with scores

        参数:
            name (KeyT): 名称。
            min (ZScoreBoundT): min。
            max (ZScoreBoundT): max。
            start (Optional[int]): start。
            num (Optional[int]): num。
            withscores (bool): withscores。
            score_cast_func (Union[Type, Callable]): scorecastfunc。

        返回:
            Awaitable: 返回处理结果。
        """
        if (start is not None and num is None) or (num is not None and start is None):
            raise DataError("``start`` and ``num`` must both be specified")
        pieces: List[EncodableT] = ["ZRANGEBYSCORE", name, min, max]
        if start is not None and num is not None:
            pieces.extend([b"LIMIT", start, num])
        if withscores:
            pieces.append(b"WITHSCORES")
        options = {"withscores": withscores, "score_cast_func": score_cast_func}
        return self.execute_command(*pieces, **options)

    def zrank(self, name: KeyT, value: EncodableT) -> Awaitable:
        """Returns a 0-based value indicating the rank of ``value`` in sorted set

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZRANK", name, value)

    def zrem(self, name: KeyT, *values: EncodableT) -> Awaitable:
        """处理zrem相关逻辑。

        参数:
            name (KeyT): 名称。
            values (*EncodableT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZREM", name, *values)

    def zremrangebylex(self, name: KeyT, min: EncodableT, max: EncodableT) -> Awaitable:
        """Remove all elements in the sorted set ``name`` between the

        参数:
            name (KeyT): 名称。
            min (EncodableT): min。
            max (EncodableT): max。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZREMRANGEBYLEX", name, min, max)

    def zremrangebyrank(self, name: KeyT, min: int, max: int) -> Awaitable:
        """Remove all elements in the sorted set ``name`` with ranks between

        参数:
            name (KeyT): 名称。
            min (int): min。
            max (int): max。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZREMRANGEBYRANK", name, min, max)

    def zremrangebyscore(self, name: KeyT, min: ZScoreBoundT, max: ZScoreBoundT) -> Awaitable:
        """Remove all elements in the sorted set ``name`` with scores

        参数:
            name (KeyT): 名称。
            min (ZScoreBoundT): min。
            max (ZScoreBoundT): max。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZREMRANGEBYSCORE", name, min, max)

    def zrevrange(
        self,
        name: KeyT,
        start: int,
        end: int,
        withscores: bool = False,
        score_cast_func: Union[Type, Callable] = float,
    ) -> Awaitable:
        """Return a range of values from sorted set ``name`` between

        参数:
            name (KeyT): 名称。
            start (int): start。
            end (int): end。
            withscores (bool): withscores。
            score_cast_func (Union[Type, Callable]): scorecastfunc。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = ["ZREVRANGE", name, start, end]
        if withscores:
            pieces.append(b"WITHSCORES")
        options = {"withscores": withscores, "score_cast_func": score_cast_func}
        return self.execute_command(*pieces, **options)

    def zrevrangebyscore(
        self,
        name: KeyT,
        min: ZScoreBoundT,
        max: ZScoreBoundT,
        start: Optional[int] = None,
        num: Optional[int] = None,
        withscores: bool = False,
        score_cast_func: Union[Type, Callable] = float,
    ) -> Awaitable:
        """Return a range of values from the sorted set ``name`` with scores

        参数:
            name (KeyT): 名称。
            min (ZScoreBoundT): min。
            max (ZScoreBoundT): max。
            start (Optional[int]): start。
            num (Optional[int]): num。
            withscores (bool): withscores。
            score_cast_func (Union[Type, Callable]): scorecastfunc。

        返回:
            Awaitable: 返回处理结果。
        """
        if (start is not None and num is None) or (num is not None and start is None):
            raise DataError("``start`` and ``num`` must both be specified")
        pieces: List[EncodableT] = ["ZREVRANGEBYSCORE", name, min, max]
        if start is not None and num is not None:
            pieces.extend([b"LIMIT", start, num])
        if withscores:
            pieces.append(b"WITHSCORES")
        options = {"withscores": withscores, "score_cast_func": score_cast_func}
        return self.execute_command(*pieces, **options)

    def zrevrank(self, name: KeyT, value: EncodableT) -> Awaitable:
        """Returns a 0-based value indicating the descending rank of

        参数:
            name (KeyT): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZREVRANK", name, value)

    def zscore(self, name: str, value: EncodableT) -> Awaitable:
        """处理zscore相关逻辑。

        参数:
            name (str): 名称。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("ZSCORE", name, value)

    def zunionstore(
        self,
        dest: KeyT,
        keys: Union[Sequence[KeyT], Mapping[AnyKeyT, float]],
        aggregate: Optional[str] = None,
    ) -> Awaitable:
        """Union multiple sorted sets specified by ``keys`` into

        参数:
            dest (KeyT): dest。
            keys (Union[Sequence[KeyT], Mapping[AnyKeyT, float]]): keys。
            aggregate (Optional[str]): aggregate。

        返回:
            Awaitable: 返回处理结果。
        """
        return self._zaggregate("ZUNIONSTORE", dest, keys, aggregate)

    def _zaggregate(
        self,
        command: str,
        dest: KeyT,
        keys: Union[Sequence[KeyT], Mapping[AnyKeyT, float]],
        aggregate: Optional[str] = None,
    ) -> Awaitable:
        """处理zaggregate相关逻辑。

        参数:
            command (str): command。
            dest (KeyT): dest。
            keys (Union[Sequence[KeyT], Mapping[AnyKeyT, float]]): keys。
            aggregate (Optional[str]): aggregate。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [command, dest, len(keys)]
        key_names: Union[Sequence[KeyT], AbstractSet[AnyKeyT]]
        weights: Optional[ValuesView[float]]
        if isinstance(keys, Mapping):
            key_names, weights = keys.keys(), keys.values()
        else:
            key_names = keys
            weights = None
        pieces.extend(key_names)
        if weights:
            pieces.append(b"WEIGHTS")
            pieces.extend(weights)
        if aggregate:
            pieces.append(b"AGGREGATE")
            pieces.append(aggregate)
        return self.execute_command(*pieces)

    # HYPERLOGLOG COMMANDS
    def pfadd(self, name: KeyT, *values: EncodableT) -> Awaitable:
        """处理pfadd相关逻辑。

        参数:
            name (KeyT): 名称。
            values (*EncodableT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("PFADD", name, *values)

    def pfcount(self, *sources: KeyT) -> Awaitable:
        """Return the approximated cardinality of

        参数:
            sources (*KeyT): sources。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("PFCOUNT", *sources)

    def pfmerge(self, dest: KeyT, *sources: KeyT) -> Awaitable:
        """处理pfmerge相关逻辑。

        参数:
            dest (KeyT): dest。
            sources (*KeyT): sources。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("PFMERGE", dest, *sources)

    # HASH COMMANDS
    def hdel(self, name: KeyT, *keys: FieldT) -> Awaitable:
        """处理hdel相关逻辑。

        参数:
            name (KeyT): 名称。
            keys (*FieldT): keys。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HDEL", name, *keys)

    def hexists(self, name: KeyT, key: FieldT) -> Awaitable:
        """处理hexists相关逻辑。

        参数:
            name (KeyT): 名称。
            key (FieldT): key。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HEXISTS", name, key)

    def hget(self, name: KeyT, key: FieldT) -> Awaitable:
        """处理hget相关逻辑。

        参数:
            name (KeyT): 名称。
            key (FieldT): key。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HGET", name, key)

    def hgetall(self, name: KeyT) -> Awaitable:
        """处理hgetall相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HGETALL", name)

    def hincrby(self, name: KeyT, key: FieldT, amount: int = 1) -> Awaitable:
        """处理hincrby相关逻辑。

        参数:
            name (KeyT): 名称。
            key (FieldT): key。
            amount (int): amount。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HINCRBY", name, key, amount)

    def hincrbyfloat(self, name: KeyT, key: FieldT, amount: float = 1.0) -> Awaitable:
        """处理hincrbyfloat相关逻辑。

        参数:
            name (KeyT): 名称。
            key (FieldT): key。
            amount (float): amount。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HINCRBYFLOAT", name, key, amount)

    def hkeys(self, name: KeyT) -> Awaitable:
        """处理hkeys相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HKEYS", name)

    def hlen(self, name: KeyT) -> Awaitable:
        """处理hlen相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HLEN", name)

    def hset(
        self,
        name: KeyT,
        key: Optional[FieldT] = None,
        value: Optional[EncodableT] = None,
        mapping: Optional[Mapping[AnyFieldT, EncodableT]] = None,
    ) -> Awaitable:
        """Set ``key`` to ``value`` within hash ``name``,

        参数:
            name (KeyT): 名称。
            key (Optional[FieldT]): key。
            value (Optional[EncodableT]): 输入值。
            mapping (Optional[Mapping[AnyFieldT, EncodableT]]): mapping。

        返回:
            Awaitable: 返回处理结果。
        """
        if key is None and not mapping:
            raise DataError("'hset' with no key value pairs")
        items: List[Union[FieldT, Optional[EncodableT]]] = []
        if key is not None:
            items.extend((key, value))
        if mapping:
            for pair in mapping.items():
                items.extend(pair)

        return self.execute_command("HSET", name, *items)

    def hsetnx(self, name: KeyT, key: FieldT, value: EncodableT) -> Awaitable:
        """Set ``key`` to ``value`` within hash ``name`` if ``key`` does not

        参数:
            name (KeyT): 名称。
            key (FieldT): key。
            value (EncodableT): 输入值。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HSETNX", name, key, value)

    def hmset(self, name: KeyT, mapping: Mapping[AnyFieldT, EncodableT]) -> Awaitable:
        """Set key to value within hash ``name`` for each corresponding

        参数:
            name (KeyT): 名称。
            mapping (Mapping[AnyFieldT, EncodableT]): mapping。

        返回:
            Awaitable: 返回处理结果。
        """
        warnings.warn(
            f"{self.__class__.__name__}.hmset() is deprecated. " f"Use {self.__class__.__name__}.hset() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not mapping:
            raise DataError("'hmset' with 'mapping' of length 0")
        items: List[Union[AnyFieldT, EncodableT]] = []
        for pair in mapping.items():
            items.extend(pair)
        return self.execute_command("HMSET", name, *items)

    def hmget(self, name: KeyT, keys: Sequence[KeyT], *args: FieldT) -> Awaitable:
        """处理hmget相关逻辑。

        参数:
            name (KeyT): 名称。
            keys (Sequence[KeyT]): keys。
            args (*FieldT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        parsed_args = list_or_args(keys, args)
        return self.execute_command("HMGET", name, *parsed_args)

    def hvals(self, name: KeyT) -> Awaitable:
        """处理hvals相关逻辑。

        参数:
            name (KeyT): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HVALS", name)

    def hstrlen(self, name: KeyT, key: FieldT) -> Awaitable:
        """Return the number of bytes stored in the value of ``key``

        参数:
            name (KeyT): 名称。
            key (FieldT): key。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("HSTRLEN", name, key)

    def publish(self, channel: ChannelT, message: EncodableT) -> Awaitable:
        """Publish ``message`` on ``channel``.

        参数:
            channel (ChannelT): 子频道。
            message (EncodableT): 消息对象。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("PUBLISH", channel, message)

    def pubsub_channels(self, pattern: PatternT = "*") -> Awaitable:
        """处理pubsubchannels相关逻辑。

        参数:
            pattern (PatternT): pattern。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("PUBSUB CHANNELS", pattern)

    def pubsub_numpat(self) -> Awaitable:
        """处理pubsubnumpat相关逻辑。"""
        return self.execute_command("PUBSUB NUMPAT")

    def pubsub_numsub(self, *args: ChannelT) -> Awaitable:
        """Return a list of (channel, number of subscribers) tuples

        参数:
            args (*ChannelT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("PUBSUB NUMSUB", *args)

    def cluster(self, cluster_arg: str, *args: str) -> Awaitable:
        """处理cluster相关逻辑。

        参数:
            cluster_arg (str): cluster参数。
            args (*str): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command(f"CLUSTER {cluster_arg.upper()}", *args)

    def eval(self, script: ScriptTextT, numkeys: int, *keys_and_参数: EncodableT) -> Awaitable:
        """Execute the Lua ``script``, specifying the ``numkeys`` the script

        参数:
            script (ScriptTextT): script。
            numkeys (int): numkeys。
            keys_and_参数 (*EncodableT): keysand参数。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("EVAL", script, numkeys, *keys_and_args)

    def evalsha(self, sha: str, numkeys: int, *keys_and_参数: EncodableT) -> Awaitable:
        """Use the ``sha`` to execute a Lua script already registered via EVAL

        参数:
            sha (str): sha。
            numkeys (int): numkeys。
            keys_and_参数 (*EncodableT): keysand参数。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("EVALSHA", sha, numkeys, *keys_and_args)

    def script_exists(self, *args: str) -> Awaitable:
        """Check if a script exists in the script cache by specifying the SHAs of

        参数:
            args (*str): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SCRIPT EXISTS", *args)

    def script_flush(self) -> Awaitable:
        """处理scriptflush相关逻辑。"""
        return self.execute_command("SCRIPT FLUSH")

    def script_kill(self) -> Awaitable:
        """处理scriptkill相关逻辑。"""
        return self.execute_command("SCRIPT KILL")

    def script_load(self, script: ScriptTextT) -> Awaitable:
        """处理scriptload相关逻辑。

        参数:
            script (ScriptTextT): script。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("SCRIPT LOAD", script)

    def register_script(self, script: ScriptTextT) -> "Script":
        """Register a Lua ``script`` specifying the ``keys`` it will touch.

        参数:
            script (ScriptTextT): script。

        返回:
            'Script': 返回处理结果。
        """
        return Script(self, script)

    # GEO COMMANDS
    def geoadd(self, name: KeyT, *values: EncodableT) -> Awaitable:
        """Add the specified geospatial items to the specified key identified

        参数:
            name (KeyT): 名称。
            values (*EncodableT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        if len(values) % 3 != 0:
            raise DataError("GEOADD requires places with lon, lat and name values")
        return self.execute_command("GEOADD", name, *values)

    def geodist(self, name: KeyT, place1: FieldT, place2: FieldT, unit: Optional[str] = None) -> Awaitable:
        """Return the distance between ``place1`` and ``place2`` members of the

        参数:
            name (KeyT): 名称。
            place1 (FieldT): place1。
            place2 (FieldT): place2。
            unit (Optional[str]): unit。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[EncodableT] = [name, place1, place2]
        if unit and unit not in ("m", "km", "mi", "ft"):
            raise DataError("GEODIST invalid unit")
        elif unit:
            pieces.append(unit)
        return self.execute_command("GEODIST", *pieces)

    def geohash(self, name: KeyT, *values: FieldT) -> Awaitable:
        """Return the geo hash string for each item of ``values`` members of

        参数:
            name (KeyT): 名称。
            values (*FieldT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("GEOHASH", name, *values)

    def geopos(self, name: KeyT, *values: FieldT) -> Awaitable:
        """Return the positions of each item of ``values`` as members of

        参数:
            name (KeyT): 名称。
            values (*FieldT): 输入值列表。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("GEOPOS", name, *values)

    def georadius(
        self,
        name: KeyT,
        longitude: float,
        latitude: float,
        radius: float,
        unit: Optional[str] = None,
        withdist: bool = False,
        withcoord: bool = False,
        withhash: bool = False,
        count: Optional[int] = None,
        sort: Optional[str] = None,
        store: Optional[KeyT] = None,
        store_dist: Optional[KeyT] = None,
    ) -> Awaitable:
        """Return the members of the specified key identified by the

        参数:
            name (KeyT): 名称。
            longitude (float): longitude。
            latitude (float): latitude。
            radius (float): radius。
            unit (Optional[str]): unit。
            withdist (bool): withdist。
            withcoord (bool): withcoord。
            withhash (bool): withhash。
            count (Optional[int]): 统计。
            sort (Optional[str]): sort。
            store (Optional[KeyT]): store。
            store_dist (Optional[KeyT]): storedist。

        返回:
            Awaitable: 返回处理结果。
        """
        return self._georadiusgeneric(
            "GEORADIUS",
            name,
            longitude,
            latitude,
            radius,
            unit=unit,
            withdist=withdist,
            withcoord=withcoord,
            withhash=withhash,
            count=count,
            sort=sort,
            store=store,
            store_dist=store_dist,
        )

    def georadiusbymember(
        self,
        name: KeyT,
        member: FieldT,
        radius: float,
        unit: Optional[str] = None,
        withdist: bool = False,
        withcoord: bool = False,
        withhash: bool = False,
        count: Optional[int] = None,
        sort: Optional[str] = None,
        store: Optional[KeyT] = None,
        store_dist: Optional[KeyT] = None,
    ) -> Awaitable:
        """This command is exactly like ``georadius`` with the sole difference

        参数:
            name (KeyT): 名称。
            member (FieldT): member。
            radius (float): radius。
            unit (Optional[str]): unit。
            withdist (bool): withdist。
            withcoord (bool): withcoord。
            withhash (bool): withhash。
            count (Optional[int]): 统计。
            sort (Optional[str]): sort。
            store (Optional[KeyT]): store。
            store_dist (Optional[KeyT]): storedist。

        返回:
            Awaitable: 返回处理结果。
        """
        return self._georadiusgeneric(
            "GEORADIUSBYMEMBER",
            name,
            member,
            radius,
            unit=unit,
            withdist=withdist,
            withcoord=withcoord,
            withhash=withhash,
            count=count,
            sort=sort,
            store=store,
            store_dist=store_dist,
        )

    def _georadiusgeneric(self, command: str, *args: EncodableT, **kwargs: Optional[EncodableT]) -> Awaitable:
        """处理georadiusgeneric相关逻辑。

        参数:
            command (str): command。
            args (*EncodableT): 可变位置参数。
            kwargs (**Optional[EncodableT]): 可变关键字参数。

        返回:
            Awaitable: 返回处理结果。
        """
        pieces: List[Optional[EncodableT]] = list(args)
        if kwargs["unit"] and kwargs["unit"] not in ("m", "km", "mi", "ft"):
            raise DataError("GEORADIUS invalid unit")
        elif kwargs["unit"]:
            pieces.append(kwargs["unit"])
        else:
            pieces.append(
                "m",
            )

        for arg_name, byte_repr in (
            ("withdist", b"WITHDIST"),
            ("withcoord", b"WITHCOORD"),
            ("withhash", b"WITHHASH"),
        ):
            if kwargs[arg_name]:
                pieces.append(byte_repr)

        if kwargs["count"]:
            pieces.extend([b"COUNT", kwargs["count"]])

        if kwargs["sort"]:
            if kwargs["sort"] == "ASC":
                pieces.append(b"ASC")
            elif kwargs["sort"] == "DESC":
                pieces.append(b"DESC")
            else:
                raise DataError("GEORADIUS invalid sort")

        if kwargs["store"] and kwargs["store_dist"]:
            raise DataError("GEORADIUS store and store_dist cant be set" " together")

        if kwargs["store"]:
            pieces.extend([b"STORE", kwargs["store"]])

        if kwargs["store_dist"]:
            pieces.extend([b"STOREDIST", kwargs["store_dist"]])

        return self.execute_command(command, *pieces, **kwargs)

    # MODULE COMMANDS
    def module_load(self, path: str) -> Awaitable:
        """Loads the module from ``path``.

        参数:
            path (str): 路径。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("MODULE LOAD", path)

    def module_unload(self, name: str) -> Awaitable:
        """Unloads the module ``name``.

        参数:
            name (str): 名称。

        返回:
            Awaitable: 返回处理结果。
        """
        return self.execute_command("MODULE UNLOAD", name)

    def module_list(self) -> Awaitable:
        """
        Returns a list of dictionaries containing the name and version of
        all loaded modules.
        """
        return self.execute_command("MODULE LIST")


StrictRedis = Redis


class MonitorCommandInfo(TypedDict):
    """处理monitorcommandinfo相关逻辑。"""
    time: float
    db: int
    client_address: str
    client_port: str
    client_type: str
    command: str


class Monitor:
    """
    Monitor is useful for handling the MONITOR command to the redis server.
    next_command() method returns one command from monitor
    listen() method yields commands from monitor.
    """

    monitor_re = re.compile(r"\[(\d+) (.*)\] (.*)")
    command_re = re.compile(r'"(.*?)(?<!\\)"')

    def __init__(self, connection_pool: ConnectionPool):
        """初始化实例。

        参数:
            connection_pool (ConnectionPool): connectionpool。
        """
        self.connection_pool = connection_pool
        self.connection: Optional[Connection] = None

    async def connect(self):
        """处理connect相关逻辑。"""
        if self.connection is None:
            self.connection = await self.connection_pool.get_connection("MONITOR")

    async def __aenter__(self):
        """实现 __aenter__ 特殊方法。"""
        await self.connect()
        self.connection = cast(Connection, self.connection)  # Connected above.
        await self.connection.send_command("MONITOR")
        # check that monitor returns 'OK', but don't return it to user
        response = await self.connection.read_response()
        if not bool_ok(response):
            raise RedisError(f"MONITOR failed: {response}")
        return self

    async def __aexit__(self, *args):
        """实现 __aexit__ 特殊方法。

        参数:
            args (*Any): 可变位置参数。
        """
        assert self.connection is not None
        await self.connection.disconnect()
        await self.connection_pool.release(self.connection)

    async def next_command(self) -> MonitorCommandInfo:
        """处理nextcommand相关逻辑。"""
        if self.connection is None:
            raise RedisError("Connection already closed.")
        await self.connect()
        response = await self.connection.read_response()
        if isinstance(response, bytes):
            response = self.connection.encoder.decode(response, force=True)
        command_time, command_data = response.split(" ", 1)
        m = self.monitor_re.match(command_data)
        if m is None:
            raise RedisError("Invalid command received.")
        db_id, client_info, command = m.groups()
        command = " ".join(self.command_re.findall(command))
        # Redis escapes double quotes because each piece of the command
        # string is surrounded by double quotes. We don't have that
        # requirement so remove the escaping and leave the quote.
        command = command.replace('\\"', '"')

        if client_info == "lua":
            client_address = "lua"
            client_port = ""
            client_type = "lua"
        elif client_info.startswith("unix"):
            client_address = "unix"
            client_port = client_info[5:]
            client_type = "unix"
        else:
            # use rsplit as ipv6 addresses contain colons
            client_address, client_port = client_info.rsplit(":", 1)
            client_type = "tcp"
        return {
            "time": float(command_time),
            "db": int(db_id),
            "client_address": client_address,
            "client_port": client_port,
            "client_type": client_type,
            "command": command,
        }

    async def listen(self) -> AsyncIterator[MonitorCommandInfo]:
        """处理listen相关逻辑。"""
        while True:
            yield await self.next_command()


class PubSub:
    """
    PubSub provides publish, subscribe and listen support to Redis channels.

    After subscribing to one or more channels, the listen() method will block
    until a message arrives on one of the subscribed channels. That message
    will be returned and it's safe to start listening again.
    """

    PUBLISH_MESSAGE_TYPES = ("message", "pmessage")
    UNSUBSCRIBE_MESSAGE_TYPES = ("unsubscribe", "punsubscribe")
    HEALTH_CHECK_MESSAGE = "aioredis-py-health-check"

    def __init__(
        self,
        connection_pool: ConnectionPool,
        shard_hint: Optional[str] = None,
        ignore_subscribe_messages: bool = False,
    ):
        """初始化实例。

        参数:
            connection_pool (ConnectionPool): connectionpool。
            shard_hint (Optional[str]): shardhint。
            ignore_subscribe_messages (bool): ignoresubscribe消息。
        """
        self.connection_pool = connection_pool
        self.shard_hint = shard_hint
        self.ignore_subscribe_messages = ignore_subscribe_messages
        self.connection: Optional[Connection] = None
        # we need to know the encoding options for this connection in order
        # to lookup channel and pattern names for callback handlers.
        self.encoder = self.connection_pool.get_encoder()
        if self.encoder.decode_responses:
            self.health_check_response: Iterable[Union[str, bytes]] = [
                "pong",
                self.HEALTH_CHECK_MESSAGE,
            ]
        else:
            self.health_check_response = [
                b"pong",
                self.encoder.encode(self.HEALTH_CHECK_MESSAGE),
            ]
        self.channels: Dict[ChannelT, PubSubHandler] = {}
        self.pending_unsubscribe_channels: Set[ChannelT] = set()
        self.patterns: Dict[ChannelT, PubSubHandler] = {}
        self.pending_unsubscribe_patterns: Set[ChannelT] = set()
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        """实现 __aenter__ 特殊方法。"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """实现 __aexit__ 特殊方法。

        参数:
            exc_type (Any): exctype。
            exc_value (Any): excvalue。
            traceback (Any): traceback。
        """
        await self.reset()

    def __del__(self):
        """实现 __del__ 特殊方法。"""
        if self.connection:
            self.connection.clear_connect_callbacks()

    async def reset(self):
        """处理重置相关逻辑。"""
        async with self._lock:
            if self.connection:
                await self.connection.disconnect()
                self.connection.clear_connect_callbacks()
                await self.connection_pool.release(self.connection)
                self.connection = None
            self.channels = {}
            self.pending_unsubscribe_channels = set()
            self.patterns = {}
            self.pending_unsubscribe_patterns = set()

    def close(self) -> Awaitable[NoReturn]:
        """处理close相关逻辑。"""
        return self.reset()

    async def on_connect(self, connection: Connection):
        """处理onconnect相关逻辑。

        参数:
            connection (Connection): connection。
        """
        # NOTE: for python3, we can't pass bytestrings as keyword arguments
        # so we need to decode channel/pattern names back to unicode strings
        # before passing them to [p]subscribe.
        self.pending_unsubscribe_channels.clear()
        self.pending_unsubscribe_patterns.clear()
        if self.channels:
            channels = {}
            for k, v in self.channels.items():
                channels[self.encoder.decode(k, force=True)] = v
            await self.subscribe(**channels)
        if self.patterns:
            patterns = {}
            for k, v in self.patterns.items():
                patterns[self.encoder.decode(k, force=True)] = v
            await self.psubscribe(**patterns)

    @property
    def subscribed(self):
        """处理subscribed相关逻辑。"""
        return bool(self.channels or self.patterns)

    async def execute_command(self, *args: EncodableT):
        """处理executecommand相关逻辑。

        参数:
            args (*EncodableT): 可变位置参数。
        """

        # NOTE: don't parse the response in this function -- it could pull a
        # legitimate message off the stack if the connection is already
        # subscribed to one or more channels

        if self.connection is None:
            self.connection = await self.connection_pool.get_connection("pubsub", self.shard_hint)
            # register a callback that re-subscribes to any channels we
            # were listening to when we were disconnected
            self.connection.register_connect_callback(self.on_connect)
        connection = self.connection
        kwargs = {"check_health": not self.subscribed}
        await self._execute(connection, connection.send_command, *args, **kwargs)

    async def _execute(self, connection, command, *args, **kwargs):
        """处理execute相关逻辑。

        参数:
            connection (Any): connection。
            command (Any): command。
            args (*Any): 可变位置参数。
            kwargs (**Any): 可变关键字参数。
        """
        try:
            return await command(*args, **kwargs)
        except (ConnectionError, TimeoutError) as e:
            await connection.disconnect()
            if not (connection.retry_on_timeout and isinstance(e, TimeoutError)):
                raise
            # Connect manually here. If the Redis server is down, this will
            # fail and raise a ConnectionError as desired.
            await connection.connect()
            # the ``on_connect`` callback should haven been called by the
            # connection to resubscribe us to any channels and patterns we were
            # previously listening to
            return await command(*args, **kwargs)

    async def parse_response(self, block: bool = True, timeout: float = 0):
        """解析response。

        参数:
            block (bool): block。
            timeout (float): timeout。
        """
        conn = self.connection
        if conn is None:
            raise RuntimeError("pubsub connection not set: " "did you forget to call subscribe() or psubscribe()?")

        await self.check_health()

        if not block and not await conn.can_read(timeout=timeout):
            return None
        response = await self._execute(conn, conn.read_response)

        if conn.health_check_interval and response == self.health_check_response:
            # ignore the health check message as user might not expect it
            return None
        return response

    async def check_health(self):
        """检查health。"""
        conn = self.connection
        if conn is None:
            raise RuntimeError("pubsub connection not set: " "did you forget to call subscribe() or psubscribe()?")

        if conn.health_check_interval and asyncio.get_event_loop().time() > conn.next_health_check:
            await conn.send_command("PING", self.HEALTH_CHECK_MESSAGE, check_health=False)

    def _normalize_keys(self, data: _NormalizeKeysT) -> _NormalizeKeysT:
        """normalize channel/pattern names to be either bytes or strings

        参数:
            data (_NormalizeKeysT): data。

        返回:
            _NormalizeKeysT: 返回处理结果。
        """
        encode = self.encoder.encode
        decode = self.encoder.decode
        return {decode(encode(k)): v for k, v in data.items()}  # type: ignore[return-value]

    async def psubscribe(self, *args: ChannelT, **kwargs: PubSubHandler):
        """Subscribe to channel patterns. Patterns supplied as keyword arguments

        参数:
            args (*ChannelT): 可变位置参数。
            kwargs (**PubSubHandler): 可变关键字参数。
        """
        parsed_args = list_or_args((args[0],), args[1:]) if args else args
        new_patterns: Dict[ChannelT, PubSubHandler] = dict.fromkeys(parsed_args)
        # Mypy bug: https://github.com/python/mypy/issues/10970
        new_patterns.update(kwargs)  # type: ignore[arg-type]
        ret_val = await self.execute_command("PSUBSCRIBE", *new_patterns.keys())
        # update the patterns dict AFTER we send the command. we don't want to
        # subscribe twice to these patterns, once for the command and again
        # for the reconnection.
        new_patterns = self._normalize_keys(new_patterns)
        self.patterns.update(new_patterns)
        self.pending_unsubscribe_patterns.difference_update(new_patterns)
        return ret_val

    def punsubscribe(self, *args: ChannelT) -> Awaitable:
        """Unsubscribe from the supplied patterns. If empty, unsubscribe from

        参数:
            args (*ChannelT): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        patterns: Iterable[ChannelT]
        if args:
            parsed_args = list_or_args((args[0],), args[1:])
            patterns = self._normalize_keys(dict.fromkeys(parsed_args)).keys()
        else:
            parsed_args = []
            patterns = self.patterns
        self.pending_unsubscribe_patterns.update(patterns)
        return self.execute_command("PUNSUBSCRIBE", *parsed_args)

    async def subscribe(self, *args: ChannelT, **kwargs: Callable):
        """Subscribe to channels. Channels supplied as keyword arguments expect

        参数:
            args (*ChannelT): 可变位置参数。
            kwargs (**Callable): 可变关键字参数。
        """
        parsed_args = list_or_args((args[0],), args[1:]) if args else ()
        new_channels = dict.fromkeys(parsed_args)
        # Mypy bug: https://github.com/python/mypy/issues/10970
        new_channels.update(kwargs)  # type: ignore[arg-type]
        ret_val = await self.execute_command("SUBSCRIBE", *new_channels.keys())
        # update the channels dict AFTER we send the command. we don't want to
        # subscribe twice to these channels, once for the command and again
        # for the reconnection.
        new_channels = self._normalize_keys(new_channels)
        self.channels.update(new_channels)
        self.pending_unsubscribe_channels.difference_update(new_channels)
        return ret_val

    def unsubscribe(self, *args) -> Awaitable:
        """Unsubscribe from the supplied channels. If empty, unsubscribe from

        参数:
            args (*Any): 可变位置参数。

        返回:
            Awaitable: 返回处理结果。
        """
        if args:
            parsed_args = list_or_args(args[0], args[1:])
            channels = self._normalize_keys(dict.fromkeys(parsed_args))
        else:
            parsed_args = []
            channels = self.channels
        self.pending_unsubscribe_channels.update(channels)
        return self.execute_command("UNSUBSCRIBE", *parsed_args)

    async def listen(self) -> AsyncIterator:
        """处理listen相关逻辑。"""
        while self.subscribed:
            response = await self.handle_message(await self.parse_response(block=True))
            if response is not None:
                yield response

    async def get_message(self, ignore_subscribe_messages: bool = False, timeout: float = 0.0):
        """Get the next message if one is available, otherwise None.

        参数:
            ignore_subscribe_messages (bool): ignoresubscribe消息。
            timeout (float): timeout。
        """
        response = await self.parse_response(block=False, timeout=timeout)
        if response:
            return await self.handle_message(response, ignore_subscribe_messages)
        return None

    def ping(self, message=None) -> Awaitable:
        """处理ping相关逻辑。

        参数:
            message (Any): 消息对象。

        返回:
            Awaitable: 返回处理结果。
        """
        message = "" if message is None else message
        return self.execute_command("PING", message)

    async def handle_message(self, response, ignore_subscribe_messages=False):
        """Parses a pub/sub message. If the channel or pattern was subscribed to

        参数:
            response (Any): response。
            ignore_subscribe_messages (Any): ignoresubscribe消息。
        """
        message_type = str_if_bytes(response[0])
        if message_type == "pmessage":
            message = {
                "type": message_type,
                "pattern": response[1],
                "channel": response[2],
                "data": response[3],
            }
        elif message_type == "pong":
            message = {
                "type": message_type,
                "pattern": None,
                "channel": None,
                "data": response[1],
            }
        else:
            message = {
                "type": message_type,
                "pattern": None,
                "channel": response[1],
                "data": response[2],
            }

        # if this is an unsubscribe message, remove it from memory
        if message_type in self.UNSUBSCRIBE_MESSAGE_TYPES:
            if message_type == "punsubscribe":
                pattern = response[1]
                if pattern in self.pending_unsubscribe_patterns:
                    self.pending_unsubscribe_patterns.remove(pattern)
                    self.patterns.pop(pattern, None)
            else:
                channel = response[1]
                if channel in self.pending_unsubscribe_channels:
                    self.pending_unsubscribe_channels.remove(channel)
                    self.channels.pop(channel, None)

        if message_type in self.PUBLISH_MESSAGE_TYPES:
            # if there's a message handler, invoke it
            if message_type == "pmessage":
                handler = self.patterns.get(message["pattern"], None)
            else:
                handler = self.channels.get(message["channel"], None)
            if handler:
                if inspect.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
                return None
        elif message_type != "pong":
            # this is a subscribe/unsubscribe message. ignore if we don't
            # want them
            if ignore_subscribe_messages or self.ignore_subscribe_messages:
                return None

        return message

    async def run(
        self,
        *,
        exception_handler: Optional["PSWorkerThreadExcHandlerT"] = None,
        poll_timeout: float = 1.0,
    ) -> None:
        """Process pub/sub messages using registered callbacks.

        参数:
            exception_handler (Optional['PSWorkerThreadExcHandlerT']): exceptionhandler。
            poll_timeout (float): polltimeout。
        """
        for channel, handler in self.channels.items():
            if handler is None:
                raise PubSubError(f"Channel: '{channel}' has no handler registered")
        for pattern, handler in self.patterns.items():
            if handler is None:
                raise PubSubError(f"Pattern: '{pattern}' has no handler registered")

        while True:
            try:
                await self.get_message(ignore_subscribe_messages=True, timeout=poll_timeout)
            except asyncio.CancelledError:
                raise
            except BaseException as e:
                if exception_handler is None:
                    raise
                res = exception_handler(e, self)
                if inspect.isawaitable(res):
                    await res
            # Ensure that other tasks on the event loop get a chance to run
            # if we didn't have to block for I/O anywhere.
            await asyncio.sleep(0)


class PubsubWorkerExceptionHandler(Protocol):
    """处理pubsubworkerexceptionhandler相关逻辑。"""
    def __call__(self, e: BaseException, pubsub: PubSub):
        """调用实例并返回结果。

        参数:
            e (BaseException): e。
            pubsub (PubSub): pubsub。
        """
        ...


class AsyncPubsubWorkerExceptionHandler(Protocol):
    """处理asyncpubsubworkerexceptionhandler相关逻辑。"""
    async def __call__(self, e: BaseException, pubsub: PubSub):
        """调用实例并返回结果。

        参数:
            e (BaseException): e。
            pubsub (PubSub): pubsub。
        """
        ...


PSWorkerThreadExcHandlerT = Union[PubsubWorkerExceptionHandler, AsyncPubsubWorkerExceptionHandler]


CommandT = Tuple[Tuple[Union[str, bytes], ...], Mapping[str, Any]]
CommandStackT = List[CommandT]


class Pipeline(Redis):  # lgtm [py/init-calls-subclass]
    """
    Pipelines provide a way to transmit multiple commands to the Redis server
    in one transmission.  This is convenient for batch processing, such as
    saving all the values in a list to Redis.

    All commands executed within a pipeline are wrapped with MULTI and EXEC
    calls. This guarantees all commands executed in the pipeline will be
    executed atomically.

    Any command raising an exception does *not* halt the execution of
    subsequent commands in the pipeline. Instead, the exception is caught
    and its instance is placed into the response list returned by execute().
    Code iterating over the response list should be able to deal with an
    instance of an exception as a potential value. In general, these will be
    ResponseError exceptions, such as those raised when issuing a command
    on a key of a different datatype.
    """

    UNWATCH_COMMANDS = {"DISCARD", "EXEC", "UNWATCH"}

    def __init__(
        self,
        connection_pool: ConnectionPool,
        response_callbacks: MutableMapping[Union[str, bytes], ResponseCallbackT],
        transaction: bool,
        shard_hint: Optional[str],
    ):
        """初始化实例。

        参数:
            connection_pool (ConnectionPool): connectionpool。
            response_callbacks (MutableMapping[Union[str, bytes], ResponseCallbackT]): responsecallbacks。
            transaction (bool): transaction。
            shard_hint (Optional[str]): shardhint。
        """
        self.connection_pool = connection_pool
        self.connection = None
        self.response_callbacks = response_callbacks
        self.is_transaction = transaction
        self.shard_hint = shard_hint
        self.watching = False
        self.command_stack: CommandStackT = []
        self.scripts: Set[Script] = set()
        self.explicit_transaction = False

    async def __aenter__(self: _RedisT) -> _RedisT:
        """实现 __aenter__ 特殊方法。"""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """实现 __aexit__ 特殊方法。

        参数:
            exc_type (Any): exctype。
            exc_value (Any): excvalue。
            traceback (Any): traceback。
        """
        await self.reset()

    def __await__(self):
        """返回可等待对象。"""
        return self._async_self().__await__()

    _DEL_MESSAGE = "Unclosed Pipeline client"

    def __len__(self):
        """返回长度。"""
        return len(self.command_stack)

    def __bool__(self):
        """返回布尔值。"""
        return True

    async def _async_self(self):
        """处理异步self相关逻辑。"""
        return self

    async def reset(self):
        """处理重置相关逻辑。"""
        self.command_stack = []
        self.scripts = set()
        # make sure to reset the connection state in the event that we were
        # watching something
        if self.watching and self.connection:
            try:
                # call this manually since our unwatch or
                # immediate_execute_command methods can call reset()
                await self.connection.send_command("UNWATCH")
                await self.connection.read_response()
            except ConnectionError:
                # disconnect will also remove any previous WATCHes
                if self.connection:
                    await self.connection.disconnect()
        # clean up the other instance attributes
        self.watching = False
        self.explicit_transaction = False
        # we can safely return the connection to the pool here since we're
        # sure we're no longer WATCHing anything
        if self.connection:
            await self.connection_pool.release(self.connection)
            self.connection = None

    def multi(self):
        """
        Start a transactional block of the pipeline after WATCH commands
        are issued. End the transactional block with `execute`.
        """
        if self.explicit_transaction:
            raise RedisError("Cannot issue nested calls to MULTI")
        if self.command_stack:
            raise RedisError("Commands without an initial WATCH have already " "been issued")
        self.explicit_transaction = True

    def execute_command(self, *args, **kwargs) -> Union["Pipeline", Awaitable["Pipeline"]]:
        """处理executecommand相关逻辑。

        参数:
            args (*Any): 可变位置参数。
            kwargs (**Any): 可变关键字参数。

        返回:
            Union['Pipeline', Awaitable['Pipeline']]: 返回处理结果。
        """
        if (self.watching or args[0] == "WATCH") and not self.explicit_transaction:
            return self.immediate_execute_command(*args, **kwargs)
        return self.pipeline_execute_command(*args, **kwargs)

    async def immediate_execute_command(self, *args, **options):
        """Execute a command immediately, but don't auto-retry on a

        参数:
            args (*Any): 可变位置参数。
            options (**Any): options。
        """
        command_name = args[0]
        conn = self.connection
        # if this is the first call, we need a connection
        if not conn:
            conn = await self.connection_pool.get_connection(command_name, self.shard_hint)
            self.connection = conn
        conn = cast(Connection, conn)
        try:
            await conn.send_command(*args)
            return await self.parse_response(conn, command_name, **options)
        except (ConnectionError, TimeoutError) as e:
            await conn.disconnect()
            # if we were already watching a variable, the watch is no longer
            # valid since this connection has died. raise a WatchError, which
            # indicates the user should retry this transaction.
            if self.watching:
                await self.reset()
                raise WatchError("A ConnectionError occurred on while watching one or more keys") from e
            # if retry_on_timeout is not set, or the error is not
            # a TimeoutError, raise it
            if not (conn.retry_on_timeout and isinstance(e, TimeoutError)):
                await self.reset()
                raise

            # retry_on_timeout is set, this is a TimeoutError and we are not
            # already WATCHing any variables. retry the command.
            try:
                await conn.send_command(*args)
                return self.parse_response(conn, command_name, **options)
            except (ConnectionError, TimeoutError):
                # a subsequent failure should simply be raised
                await self.reset()
                raise
        except asyncio.CancelledError:
            await conn.disconnect()
            raise

    def pipeline_execute_command(self, *args, **options):
        """Stage a command to be executed when execute() is next called

        参数:
            args (*Any): 可变位置参数。
            options (**Any): options。
        """
        self.command_stack.append((args, options))
        return self

    async def _execute_transaction(self, connection: Connection, commands: CommandStackT, raise_on_error):  # noqa: C901
        """处理executetransaction相关逻辑。

        参数:
            connection (Connection): connection。
            commands (CommandStackT): commands。
            raise_on_error (Any): raiseonerror。
        """
        pre: CommandT = (("MULTI",), {})
        post: CommandT = (("EXEC",), {})
        cmds = (pre, *commands, post)
        all_cmds = connection.pack_commands(args for args, options in cmds if EMPTY_RESPONSE not in options)
        await connection.send_packed_command(all_cmds)
        errors = []

        # parse off the response for MULTI
        # NOTE: we need to handle ResponseErrors here and continue
        # so that we read all the additional command messages from
        # the socket
        try:
            await self.parse_response(connection, "_")
        except ResponseError as err:
            errors.append((0, err))

        # and all the other commands
        for i, command in enumerate(commands):
            if EMPTY_RESPONSE in command[1]:
                errors.append((i, command[1][EMPTY_RESPONSE]))
            else:
                try:
                    await self.parse_response(connection, "_")
                except ResponseError as err:
                    self.annotate_exception(err, i + 1, command[0])
                    errors.append((i, err))

        # parse the EXEC.
        try:
            response = await self.parse_response(connection, "_")
        except ExecAbortError as err:
            if errors:
                raise errors[0][1] from err
            raise

        # EXEC clears any watched keys
        self.watching = False

        if response is None:
            raise WatchError("Watched variable changed.") from None

        # put any parse errors into the response
        for i, e in errors:
            response.insert(i, e)

        if len(response) != len(commands):
            if self.connection:
                await self.connection.disconnect()
            raise ResponseError("Wrong number of response items from pipeline execution") from None

        # find any errors in the response and raise if necessary
        if raise_on_error:
            self.raise_first_error(commands, response)

        # We have to run response callbacks manually
        data = []
        for r, cmd in zip(response, commands):
            if not isinstance(r, Exception):
                args, options = cmd
                command_name = args[0]
                if command_name in self.response_callbacks:
                    r = self.response_callbacks[command_name](r, **options)
                    if inspect.isawaitable(r):
                        r = await r
            data.append(r)
        return data

    async def _execute_pipeline(self, connection: Connection, commands: CommandStackT, raise_on_error: bool):
        # build up all commands into a single request to increase network perf
        """处理executepipeline相关逻辑。

        参数:
            connection (Connection): connection。
            commands (CommandStackT): commands。
            raise_on_error (bool): raiseonerror。
        """
        all_cmds = connection.pack_commands([args for args, _ in commands])
        await connection.send_packed_command(all_cmds)

        response = []
        for args, options in commands:
            try:
                response.append(await self.parse_response(connection, args[0], **options))
            except ResponseError as e:
                response.append(e)

        if raise_on_error:
            self.raise_first_error(commands, response)
        return response

    def raise_first_error(self, commands: CommandStackT, response: Iterable[Any]):
        """处理raisefirsterror相关逻辑。

        参数:
            commands (CommandStackT): commands。
            response (Iterable[Any]): response。
        """
        for i, r in enumerate(response):
            if isinstance(r, ResponseError):
                self.annotate_exception(r, i + 1, commands[i][0])
                raise r

    def annotate_exception(self, exception: Exception, number: int, command: Iterable[object]) -> None:
        """处理annotateexception相关逻辑。

        参数:
            exception (Exception): exception。
            number (int): number。
            command (Iterable[object]): command。
        """
        cmd = " ".join(map(safe_str, command))
        msg = f"Command # {number} ({cmd}) of pipeline caused error: {exception.args}"
        exception.args = (msg,) + exception.args[1:]

    def parse_response(self, connection: Connection, command_name: Union[str, bytes], **options):
        """解析response。

        参数:
            connection (Connection): connection。
            command_name (Union[str, bytes]): command名称。
            options (**Any): options。
        """
        result = super().parse_response(connection, command_name, **options)
        if command_name in self.UNWATCH_COMMANDS:
            self.watching = False
        elif command_name == "WATCH":
            self.watching = True
        return result

    async def load_scripts(self):
        # make sure all scripts that are about to be run on this pipeline exist
        """加载scripts。"""
        scripts = list(self.scripts)
        immediate = self.immediate_execute_command
        shas = [s.sha for s in scripts]
        # we can't use the normal script_* methods because they would just
        # get buffered in the pipeline.
        exists = await immediate("SCRIPT EXISTS", *shas)
        if not all(exists):
            for s, exist in zip(scripts, exists):
                if not exist:
                    s.sha = await immediate("SCRIPT LOAD", s.script)

    async def execute(self, raise_on_error: bool = True):
        """处理execute相关逻辑。

        参数:
            raise_on_error (bool): raiseonerror。
        """
        stack = self.command_stack
        if not stack and not self.watching:
            return []
        if self.scripts:
            await self.load_scripts()
        if self.is_transaction or self.explicit_transaction:
            execute = self._execute_transaction
        else:
            execute = self._execute_pipeline

        conn = self.connection
        if not conn:
            conn = await self.connection_pool.get_connection("MULTI", self.shard_hint)
            # assign to self.connection so reset() releases the connection
            # back to the pool after we're done
            self.connection = conn
        conn = cast(Connection, conn)

        try:
            return await execute(conn, stack, raise_on_error)
        except (ConnectionError, TimeoutError) as e:
            await conn.disconnect()
            # if we were watching a variable, the watch is no longer valid
            # since this connection has died. raise a WatchError, which
            # indicates the user should retry this transaction.
            if self.watching:
                raise WatchError("A ConnectionError occurred on while " "watching one or more keys") from e
            # if retry_on_timeout is not set, or the error is not
            # a TimeoutError, raise it
            if not (conn.retry_on_timeout and isinstance(e, TimeoutError)):
                raise
            # retry a TimeoutError when retry_on_timeout is set
            return await execute(conn, stack, raise_on_error)
        finally:
            await self.reset()

    async def watch(self, *names: KeyT):
        """处理watch相关逻辑。

        参数:
            names (*KeyT): names。
        """
        if self.explicit_transaction:
            raise RedisError("Cannot issue a WATCH after a MULTI")
        return await self.execute_command("WATCH", *names)

    async def unwatch(self):
        """处理unwatch相关逻辑。"""
        return self.watching and await self.execute_command("UNWATCH") or True


class Script:
    """An executable Lua script object returned by ``register_script``"""

    def __init__(self, registered_client: Redis, script: ScriptTextT):
        """初始化实例。

        参数:
            registered_client (Redis): registeredclient。
            script (ScriptTextT): script。
        """
        self.registered_client = registered_client
        self.script = script
        # Precalculate and store the SHA1 hex digest of the script.

        if isinstance(script, str):
            # We need the encoding from the client in order to generate an
            # accurate byte representation of the script
            encoder = registered_client.connection_pool.get_encoder()
            script_bytes = encoder.encode(script)
        else:
            script_bytes = script
        self.sha = hashlib.sha1(script_bytes).hexdigest()

    async def __call__(
        self,
        keys: Optional[Sequence[KeyT]] = None,
        args: Optional[Iterable[EncodableT]] = None,
        client: Optional[Redis] = None,
    ):
        """调用实例并返回结果。

        参数:
            keys (Optional[Sequence[KeyT]]): keys。
            args (Optional[Iterable[EncodableT]]): 可变位置参数。
            client (Optional[Redis]): client。
        """
        keys = keys or []
        args = args or []
        if client is None:
            client = self.registered_client
        args = tuple(keys) + tuple(args)
        # make sure the Redis server knows about the script
        if isinstance(client, Pipeline):
            # Make sure the pipeline can register the script before executing.
            client.scripts.add(self)
            return client.evalsha(self.sha, len(keys), *args)
        try:
            return await client.evalsha(self.sha, len(keys), *args)
        except NoScriptError:
            # Maybe the client is pointed to a differnet server than the client
            # that created this instance?
            # Overwrite the sha just in case there was a discrepancy.
            self.sha = await client.script_load(self.script)
            return await client.evalsha(self.sha, len(keys), *args)


class BitFieldOperation:
    """
    Command builder for BITFIELD commands.
    """

    def __init__(self, client: Redis, key: KeyT, default_overflow: Optional[str] = None):
        """初始化实例。

        参数:
            client (Redis): client。
            key (KeyT): key。
            default_overflow (Optional[str]): defaultoverflow。
        """
        self.client = client
        self.key = key
        self._default_overflow = default_overflow
        self.operations: List[Tuple[EncodableT, ...]] = []
        self._last_overflow = "WRAP"
        self.reset()

    def reset(self):
        """处理重置相关逻辑。"""
        self.operations = []
        self._last_overflow = "WRAP"
        self.overflow(self._default_overflow or self._last_overflow)

    def overflow(self, overflow: str):
        """Update the overflow algorithm of successive INCRBY operations

        参数:
            overflow (str): overflow。
        """
        overflow = overflow.upper()
        if overflow != self._last_overflow:
            self._last_overflow = overflow
            self.operations.append(("OVERFLOW", overflow))
        return self

    def incrby(
        self,
        fmt: str,
        offset: BitfieldOffsetT,
        increment: int,
        overflow: Optional[str] = None,
    ):
        """Increment a bitfield by a given amount.

        参数:
            fmt (str): fmt。
            offset (BitfieldOffsetT): offset。
            increment (int): increment。
            overflow (Optional[str]): overflow。
        """
        if overflow is not None:
            self.overflow(overflow)

        self.operations.append(("INCRBY", fmt, offset, increment))
        return self

    def get(self, fmt: str, offset: BitfieldOffsetT):
        """Get the value of a given bitfield.

        参数:
            fmt (str): fmt。
            offset (BitfieldOffsetT): offset。
        """
        self.operations.append(("GET", fmt, offset))
        return self

    def set(self, fmt: str, offset: BitfieldOffsetT, value: int):
        """Set the value of a given bitfield.

        参数:
            fmt (str): fmt。
            offset (BitfieldOffsetT): offset。
            value (int): 输入值。
        """
        self.operations.append(("SET", fmt, offset, value))
        return self

    @property
    def command(self):
        """处理command相关逻辑。"""
        cmd: List[EncodableT] = ["BITFIELD", self.key]
        for ops in self.operations:
            cmd.extend(ops)
        return cmd

    def execute(self):
        """
        Execute the operation(s) in a single BITFIELD command. The return value
        is a list of values corresponding to each operation. If the client
        used to create this instance was a pipeline, the list of values
        will be present within the pipeline's execute.
        """
        command = self.command
        self.reset()
        return self.client.execute_command(*command)
