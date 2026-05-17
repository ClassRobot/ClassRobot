from __future__ import annotations

import asyncio
import gc
import sqlite3
import shutil
from datetime import date as date_value, datetime, time, timedelta
from pathlib import Path
from typing import Any

from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from utils.models import Classes, Group, GroupBind, User
from core.storage import (
    MESSAGE_DB_NAME,
    MESSAGE_TABLE_NAME,
    ChatHistoryStore,
    MessageOwnerKind,
    parse_metadata,
    storage_manager,
)
from core.storage.files import sanitize_owner_id


def _space_root(kind: str) -> Path:
    """返回聊天记录空间类型对应的根目录。

    Args:
        kind: 聊天记录空间类型，仅支持 ``user`` 与 ``group``。

    Returns:
        Path: 指定类型在 storage 下的根目录。

    Raises:
        ValueError: 当空间类型不受支持时抛出。
    """

    if kind == "user":
        return storage_manager.root / "users"
    if kind == "group":
        return storage_manager.root / "groups"
    raise ValueError("Unsupported chat history kind")


def _chat_db_path(kind: str, owner_id: str) -> Path:
    """返回指定聊天空间的 SQLite 数据库路径。

    Args:
        kind: 聊天记录空间类型。
        owner_id: 空间所属实体 ID。

    Returns:
        Path: ``messages.db`` 的绝对路径。
    """

    normalized_owner_id = sanitize_owner_id(owner_id)
    return _space_root(kind) / normalized_owner_id / "chat" / MESSAGE_DB_NAME


def _existing_chat_db(kind: str, owner_id: str) -> Path:
    """返回已存在的聊天记录数据库路径。

    Args:
        kind: 聊天记录空间类型。
        owner_id: 空间所属实体 ID。

    Returns:
        Path: 目标聊天数据库绝对路径。

    Raises:
        FileNotFoundError: 当聊天记录数据库不存在时抛出。
    """

    db_path = _chat_db_path(kind, owner_id)
    if not db_path.exists() or not db_path.is_file():
        raise FileNotFoundError(f"Chat history not found: {kind}/{sanitize_owner_id(owner_id)}")
    return db_path


def _scan_owner_ids(kind: str) -> list[str]:
    """扫描磁盘中已经存在聊天数据库的空间 ID。

    Args:
        kind: 聊天记录空间类型。

    Returns:
        list[str]: 含聊天数据库的空间拥有者 ID 列表。
    """

    root = _space_root(kind)
    if not root.exists():
        return []

    owner_ids: list[str] = []
    for child in root.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        db_path = child / "chat" / MESSAGE_DB_NAME
        if db_path.exists() and db_path.is_file():
            owner_ids.append(child.name)
    return sorted(owner_ids)


def _connect(db_path: Path, kind: str | None = None, owner_id: str | None = None) -> sqlite3.Connection:
    """打开 SQLite 连接并配置为行字典访问。

    Args:
        db_path: 聊天记录数据库路径。
        kind: 可选的聊天记录空间类型，用于读取前补齐旧表结构。
        owner_id: 可选的空间拥有者 ID，用于旧表迁移时回填归属。

    Returns:
        sqlite3.Connection: 已配置 ``row_factory`` 的连接对象。
    """

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    if kind is not None and owner_id is not None:
        ChatHistoryStore._ensure_schema(connection, MessageOwnerKind(kind), sanitize_owner_id(owner_id))  # noqa: SLF001
    return connection


def _message_table_exists(connection: sqlite3.Connection) -> bool:
    """判断数据库中是否存在统一消息表。

    Args:
        connection: 当前 SQLite 连接。

    Returns:
        bool: 存在消息表时返回 ``True``。
    """

    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (MESSAGE_TABLE_NAME,),
    ).fetchone()
    return row is not None


def _space_stats(kind: str, owner_id: str, db_path: Path) -> dict[str, Any]:
    """统计单个聊天空间中的消息概况。

    Args:
        kind: 聊天记录空间类型。
        owner_id: 空间所属实体 ID。
        db_path: 聊天记录数据库路径。

    Returns:
        dict[str, Any]: 消息总数、角色分布、最近一条消息摘要等统计结果。
    """

    record_counts = {"collect": 0, "chat": 0}
    actor_counts = {"user": 0, "assistant": 0, "system": 0}
    direction_counts = {"inbound": 0, "outbound": 0}

    with _connect(db_path, kind, owner_id) as connection:
        if not _message_table_exists(connection):
            return {
                "message_count": 0,
                "participant_count": 0,
                "record_counts": record_counts,
                "actor_counts": actor_counts,
                "direction_counts": direction_counts,
                "latest_message_at": None,
                "latest_message_preview": "",
                "latest_message_user_name": "",
                "latest_message_actor_role": "",
                "latest_message_record_kind": "",
                "latest_message_direction": "",
                "db_size": db_path.stat().st_size,
            }

        total_row = connection.execute(
            f"SELECT COUNT(*) AS total, COUNT(DISTINCT user_id) AS participants FROM {MESSAGE_TABLE_NAME}"
        ).fetchone()
        grouped_record_kinds = connection.execute(
            f"""
            SELECT record_kind, COUNT(*) AS total
            FROM {MESSAGE_TABLE_NAME}
            GROUP BY record_kind
            """
        ).fetchall()
        grouped_actor_roles = connection.execute(
            f"""
            SELECT actor_role, COUNT(*) AS total
            FROM {MESSAGE_TABLE_NAME}
            GROUP BY actor_role
            """
        ).fetchall()
        grouped_directions = connection.execute(
            f"""
            SELECT direction, COUNT(*) AS total
            FROM {MESSAGE_TABLE_NAME}
            GROUP BY direction
            """
        ).fetchall()
        latest_row = connection.execute(
            f"""
            SELECT user_name, plain_text, raw_text, created_at, actor_role, record_kind, direction
            FROM {MESSAGE_TABLE_NAME}
            ORDER BY created_ts DESC, id DESC
            LIMIT 1
            """
        ).fetchone()

    for row in grouped_record_kinds:
        kind = str(row["record_kind"])
        if kind in record_counts:
            record_counts[kind] = int(row["total"])

    for row in grouped_actor_roles:
        role = str(row["actor_role"])
        if role in actor_counts:
            actor_counts[role] = int(row["total"])

    for row in grouped_directions:
        direction = str(row["direction"])
        if direction in direction_counts:
            direction_counts[direction] = int(row["total"])

    latest_preview = ""
    latest_user_name = ""
    latest_actor_role = ""
    latest_record_kind = ""
    latest_direction = ""
    latest_message_at = None
    if latest_row is not None:
        latest_preview = str(latest_row["plain_text"] or latest_row["raw_text"] or "")
        latest_user_name = str(latest_row["user_name"] or "")
        latest_actor_role = str(latest_row["actor_role"] or "")
        latest_record_kind = str(latest_row["record_kind"] or "")
        latest_direction = str(latest_row["direction"] or "")
        latest_message_at = str(latest_row["created_at"] or "")

    return {
        "message_count": int(total_row["total"]) if total_row is not None else 0,
        "participant_count": int(total_row["participants"]) if total_row is not None else 0,
        "record_counts": record_counts,
        "actor_counts": actor_counts,
        "direction_counts": direction_counts,
        "latest_message_at": latest_message_at,
        "latest_message_preview": latest_preview,
        "latest_message_user_name": latest_user_name,
        "latest_message_actor_role": latest_actor_role,
        "latest_message_record_kind": latest_record_kind,
        "latest_message_direction": latest_direction,
        "db_size": db_path.stat().st_size,
    }


async def _space_indexes(
    kind: str,
    owner_ids: list[str],
) -> tuple[dict[str, User], dict[str, Group], dict[int, list[GroupBind]]]:
    """批量加载聊天空间对应的用户或群组实体。

    Args:
        kind: 聊天记录空间类型。
        owner_ids: 需要映射的空间拥有者 ID 列表。

    Returns:
        tuple[dict[str, User], dict[str, Group], dict[int, list[GroupBind]]]:
            用户索引、群组索引、群组绑定列表索引。
    """

    user_index: dict[str, User] = {}
    group_index: dict[str, Group] = {}
    binds_by_group: dict[int, list[GroupBind]] = {}
    if not owner_ids:
        return user_index, group_index, binds_by_group

    async with get_session() as session:
        if kind == "user":
            user_ids = [int(owner_id) for owner_id in owner_ids if owner_id.isdigit()]
            if not user_ids:
                return user_index, group_index, binds_by_group
            users = await session.scalars(select(User).where(User.id.in_(user_ids)))
            user_index = {str(user.id): user for user in users}
            return user_index, group_index, binds_by_group

        group_ids = [int(owner_id) for owner_id in owner_ids if owner_id.isdigit()]
        if not group_ids:
            return user_index, group_index, binds_by_group

        groups = await session.scalars(
            select(Group)
            .where(Group.id.in_(group_ids))
            .options(
                selectinload(Group.creator),
                selectinload(Group.classes),
            )
        )
        group_list = list(groups)
        group_index = {str(group.id): group for group in group_list}

        binds = await session.scalars(select(GroupBind).where(GroupBind.group_id.in_(group_ids)).order_by(GroupBind.id))
        for bind in binds:
            binds_by_group.setdefault(bind.group_id, []).append(bind)
    return user_index, group_index, binds_by_group


def _owner_payload(
    kind: str,
    owner_id: str,
    user_index: dict[str, User],
    group_index: dict[str, Group],
    binds_by_group: dict[int, list[GroupBind]],
) -> dict[str, Any]:
    """构造聊天空间所属实体的展示信息。

    Args:
        kind: 聊天记录空间类型。
        owner_id: 空间拥有者 ID。
        user_index: 用户索引。
        group_index: 群组索引。
        binds_by_group: 群组绑定索引。

    Returns:
        dict[str, Any]: 标题、副标题、关联状态和实体摘要。
    """

    if kind == "user":
        user = user_index.get(owner_id)
        if user is None:
            return {
                "title": f"用户 {owner_id}",
                "subtitle": "未在数据库中找到关联用户",
                "linked": False,
                "owner": None,
            }
        return {
            "title": user.nickname or user.username or f"用户 {owner_id}",
            "subtitle": user.username,
            "linked": True,
            "owner": {
                "type": "user",
                "id": user.id,
                "nickname": user.nickname,
                "username": user.username,
                "avatar": user.avatar,
            },
        }

    group = group_index.get(owner_id)
    if group is None:
        return {
            "title": f"群组 {owner_id}",
            "subtitle": "未在数据库中找到关联群组",
            "linked": False,
            "owner": None,
        }

    classes = getattr(group, "classes", None)
    binds = binds_by_group.get(group.id, [])
    platforms = sorted({bind.platform_id for bind in binds})
    channel_ids = [bind.channel_id for bind in binds]
    title = classes.name if isinstance(classes, Classes) else group.name
    if binds:
        subtitle = " / ".join(
            filter(
                None,
                [
                    ", ".join(platforms[:2]),
                    channel_ids[0],
                ],
            )
        )
    else:
        subtitle = group.name
    return {
        "title": title,
        "subtitle": subtitle,
        "linked": True,
        "owner": {
            "type": "group",
            "group_id": group.id,
            "group_name": group.name,
            "class_id": classes.id if isinstance(classes, Classes) else None,
            "class_name": classes.name if isinstance(classes, Classes) else None,
            "creator": (
                {
                    "id": group.creator.id,
                    "nickname": group.creator.nickname,
                    "username": group.creator.username,
                    "avatar": group.creator.avatar,
                }
                if group.creator is not None
                else None
            ),
            "bind_count": len(binds),
            "platforms": platforms,
            "channels": channel_ids,
        },
    }


def _space_summary(
    kind: str,
    owner_id: str,
    owner_payload: dict[str, Any],
    db_path: Path,
) -> dict[str, Any]:
    """构造聊天空间摘要。

    Args:
        kind: 聊天记录空间类型。
        owner_id: 空间拥有者 ID。
        owner_payload: 关联实体信息。
        db_path: 聊天数据库路径。

    Returns:
        dict[str, Any]: 可供列表与详情共用的聊天空间摘要。
    """

    stats = _space_stats(kind, owner_id, db_path)
    return {
        "key": f"{kind}:{owner_id}",
        "kind": kind,
        "owner_id": owner_id,
        "title": owner_payload["title"],
        "subtitle": owner_payload["subtitle"],
        "linked": owner_payload["linked"],
        "owner": owner_payload["owner"],
        "chat_path": str(db_path.parent),
        "db_path": str(db_path),
        **stats,
    }


def _validate_record_kind(record_kind: str | None) -> str | None:
    """校验消息记录类型过滤参数。

    Args:
        record_kind: 前端提交的记录类型。

    Returns:
        str | None: 合法记录类型或 ``None``。

    Raises:
        ValueError: 当记录类型不在允许范围内时抛出。
    """

    if record_kind in {None, "", "all"}:
        return None
    if record_kind not in {"collect", "chat"}:
        raise ValueError("Unsupported chat history record kind")
    return record_kind


def _validate_actor_role(actor_role: str | None) -> str | None:
    """校验消息角色过滤参数。

    Args:
        actor_role: 前端提交的消息角色。

    Returns:
        str | None: 合法角色或 ``None``。

    Raises:
        ValueError: 当角色不在允许范围内时抛出。
    """

    if actor_role in {None, "", "all"}:
        return None
    if actor_role not in {"user", "assistant", "system"}:
        raise ValueError("Unsupported chat history actor role")
    return actor_role


def _validate_direction(direction: str | None) -> str | None:
    """校验消息方向过滤参数。

    Args:
        direction: 前端提交的消息方向。

    Returns:
        str | None: 合法方向或 ``None``。

    Raises:
        ValueError: 当方向不在允许范围内时抛出。
    """

    if direction in {None, "", "all"}:
        return None
    if direction not in {"inbound", "outbound"}:
        raise ValueError("Unsupported chat history message direction")
    return direction


def _validate_message_date(message_date: str | None) -> str | None:
    """校验指定日期过滤参数。

    Args:
        message_date: 前端提交的日期字符串，格式应为 ``YYYY-MM-DD``。

    Returns:
        str | None: 规范化后的日期字符串或 ``None``。

    Raises:
        ValueError: 当日期格式不合法时抛出。
    """

    if message_date in {None, ""}:
        return None
    normalized_date = str(message_date).strip()
    try:
        return date_value.fromisoformat(normalized_date).isoformat()
    except ValueError as error:
        raise ValueError("Unsupported chat history message date, expected YYYY-MM-DD") from error


def _message_query_parts(
    *,
    q: str | None,
    record_kind: str | None,
    actor_role: str | None,
    direction: str | None,
    message_date: str | None,
) -> tuple[str, list[Any]]:
    """构造消息查询公用的 WHERE 条件。

    Args:
        q: 关键词检索条件。
        record_kind: 记录类型过滤。
        actor_role: 消息角色过滤。
        direction: 消息方向过滤。
        message_date: 指定日期过滤，仅保留当天消息。

    Returns:
        tuple[str, list[Any]]: SQL WHERE 子句和绑定参数列表。
    """

    conditions: list[str] = []
    params: list[Any] = []

    if record_kind:
        conditions.append("record_kind = ?")
        params.append(record_kind)

    if actor_role:
        conditions.append("actor_role = ?")
        params.append(actor_role)

    if direction:
        conditions.append("direction = ?")
        params.append(direction)

    if message_date:
        selected_date = date_value.fromisoformat(message_date)
        start_at = datetime.combine(selected_date, time.min)
        end_at = start_at + timedelta(days=1)
        conditions.append("created_ts >= ?")
        params.append(int(start_at.timestamp()))
        conditions.append("created_ts < ?")
        params.append(int(end_at.timestamp()))

    keyword = str(q or "").strip().lower()
    if keyword:
        for term in [item for item in keyword.split(" ") if item]:
            conditions.append(
                """
                instr(
                    lower(
                        coalesce(user_name, '') || ' ' ||
                        coalesce(plain_text, '') || ' ' ||
                        coalesce(raw_text, '')
                    ),
                    ?
                ) > 0
                """
            )
            params.append(term)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_sql, params


def _available_message_dates(
    connection: sqlite3.Connection,
    *,
    q: str | None,
    record_kind: str | None,
    actor_role: str | None,
    direction: str | None,
) -> list[str]:
    """读取当前过滤条件下存在消息的日期列表。

    Args:
        connection: 当前聊天记录数据库连接。
        q: 可选的关键词过滤。
        record_kind: 可选的消息类型过滤。
        actor_role: 可选的消息角色过滤。
        direction: 可选的消息方向过滤。

    Returns:
        list[str]: 按日期倒序排列的 ``YYYY-MM-DD`` 列表。
    """

    where_sql, params = _message_query_parts(
        q=q,
        record_kind=record_kind,
        actor_role=actor_role,
        direction=direction,
        message_date=None,
    )
    rows = connection.execute(
        f"""
        SELECT substr(created_at, 1, 10) AS message_date
        FROM {MESSAGE_TABLE_NAME}
        {where_sql}
        GROUP BY substr(created_at, 1, 10)
        ORDER BY message_date DESC
        """,
        tuple(params),
    ).fetchall()

    available_dates: list[str] = []
    for row in rows:
        raw_date = str(row["message_date"] or "").strip()
        if not raw_date:
            continue
        try:
            available_dates.append(date_value.fromisoformat(raw_date).isoformat())
        except ValueError:
            continue
    return available_dates


def _message_payload(row: sqlite3.Row) -> dict[str, Any]:
    """把 SQLite 消息行转换成接口响应结构。

    Args:
        row: SQLite 行对象。

    Returns:
        dict[str, Any]: 单条消息记录的接口数据。
    """

    return {
        "event_key": str(row["event_key"]),
        "owner_kind": str(row["owner_kind"] or ""),
        "owner_id": str(row["owner_id"] or ""),
        "record_kind": str(row["record_kind"]),
        "direction": str(row["direction"] or ""),
        "actor_role": str(row["actor_role"]),
        "message_id": str(row["message_id"] or ""),
        "user_id": str(row["user_id"]),
        "user_name": str(row["user_name"]),
        "plain_text": str(row["plain_text"]),
        "raw_text": str(row["raw_text"] or ""),
        "display_text": str(row["plain_text"] or row["raw_text"] or ""),
        "created_at": str(row["created_at"]),
        "platform": str(row["platform"] or ""),
        "platform_name": str(row["platform_name"] or ""),
        "channel_id": str(row["channel_id"]) if row["channel_id"] not in (None, "") else None,
        "guild_id": str(row["guild_id"]) if row["guild_id"] not in (None, "") else None,
        "bot_id": str(row["bot_id"] or ""),
        "platform_user_id": str(row["platform_user_id"] or ""),
        "metadata": parse_metadata(row["metadata"]),
    }


async def list_chat_spaces(*, kind: str | None = None, q: str | None = None) -> dict[str, Any]:
    """列出当前系统中可查看聊天记录的空间。

    Args:
        kind: 可选的空间类型过滤条件。
        q: 可选的空间搜索词。

    Returns:
        dict[str, Any]: 聊天空间列表与统计信息。
    """

    kinds = [kind] if kind else ["user", "group"]
    items: list[dict[str, Any]] = []
    keyword = (q or "").strip().lower()

    for current_kind in kinds:
        owner_ids = _scan_owner_ids(current_kind)
        user_index, group_index, binds_by_group = await _space_indexes(current_kind, owner_ids)
        for owner_id in owner_ids:
            owner_payload = _owner_payload(current_kind, owner_id, user_index, group_index, binds_by_group)
            item = _space_summary(current_kind, owner_id, owner_payload, _chat_db_path(current_kind, owner_id))
            if keyword:
                haystacks = [
                    item["title"],
                    item["subtitle"],
                    item["owner_id"],
                    item["latest_message_preview"],
                    item["latest_message_user_name"],
                ]
                owner = item.get("owner")
                if isinstance(owner, dict):
                    haystacks.extend(
                        [
                            owner.get("username"),
                            owner.get("nickname"),
                            owner.get("group_name"),
                            owner.get("class_name"),
                            " ".join(owner.get("platforms", [])) if isinstance(owner.get("platforms"), list) else "",
                            " ".join(owner.get("channels", [])) if isinstance(owner.get("channels"), list) else "",
                        ]
                    )
                if not any(keyword in str(value or "").lower() for value in haystacks):
                    continue
            items.append(item)

    items.sort(
        key=lambda item: (
            item.get("latest_message_at") or "",
            item["kind"],
            item["owner_id"],
        ),
        reverse=True,
    )
    return {
        "items": items,
        "total": len(items),
        "root": str(storage_manager.root),
    }


async def get_chat_space_detail(kind: str, owner_id: str) -> dict[str, Any]:
    """读取单个聊天空间的摘要详情。

    Args:
        kind: 聊天记录空间类型。
        owner_id: 空间拥有者 ID。

    Returns:
        dict[str, Any]: 聊天空间详情。
    """

    db_path = _existing_chat_db(kind, owner_id)
    user_index, group_index, binds_by_group = await _space_indexes(kind, [sanitize_owner_id(owner_id)])
    owner_payload = _owner_payload(kind, sanitize_owner_id(owner_id), user_index, group_index, binds_by_group)
    return _space_summary(kind, sanitize_owner_id(owner_id), owner_payload, db_path)


async def list_chat_messages(
    kind: str,
    owner_id: str,
    *,
    q: str | None = None,
    record_kind: str | None = None,
    actor_role: str | None = None,
    direction: str | None = None,
    message_date: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """按日期读取指定聊天空间中的消息记录。

    Args:
        kind: 聊天记录空间类型。
        owner_id: 空间拥有者 ID。
        q: 可选的消息关键词搜索词。
        record_kind: 可选的消息记录类型过滤。
        actor_role: 可选的消息主体角色过滤。
        direction: 可选的消息方向过滤。
        message_date: 可选的消息日期；未提供时默认返回最新一天。
        page: 兼容保留参数，当前固定返回第 1 页。
        page_size: 兼容保留参数，当前按日期返回当天全部消息。

    Returns:
        dict[str, Any]: 指定日期对应的消息列表。
    """

    db_path = _existing_chat_db(kind, owner_id)
    normalized_record_kind = _validate_record_kind(record_kind)
    normalized_actor_role = _validate_actor_role(actor_role)
    normalized_direction = _validate_direction(direction)
    normalized_message_date = _validate_message_date(message_date)

    with _connect(db_path, kind, owner_id) as connection:
        if not _message_table_exists(connection):
            return {
                "kind": kind,
                "owner_id": sanitize_owner_id(owner_id),
                "q": str(q or "").strip(),
                "record_kind": normalized_record_kind,
                "actor_role": normalized_actor_role,
                "direction": normalized_direction,
                "message_date": normalized_message_date,
                "available_dates": [],
                "items": [],
                "page": page,
                "page_size": page_size,
                "total": 0,
            }

        available_dates = _available_message_dates(
            connection,
            q=q,
            record_kind=normalized_record_kind,
            actor_role=normalized_actor_role,
            direction=normalized_direction,
        )
        effective_message_date = normalized_message_date if normalized_message_date in available_dates else None
        if not effective_message_date and available_dates:
            effective_message_date = available_dates[0]

        if not effective_message_date:
            return {
                "kind": kind,
                "owner_id": sanitize_owner_id(owner_id),
                "q": str(q or "").strip(),
                "record_kind": normalized_record_kind,
                "actor_role": normalized_actor_role,
                "direction": normalized_direction,
                "message_date": None,
                "available_dates": available_dates,
                "items": [],
                "page": 1,
                "page_size": 0,
                "total": 0,
            }

        where_sql, params = _message_query_parts(
            q=q,
            record_kind=normalized_record_kind,
            actor_role=normalized_actor_role,
            direction=normalized_direction,
            message_date=effective_message_date,
        )
        total_row = connection.execute(
            f"SELECT COUNT(*) AS total FROM {MESSAGE_TABLE_NAME} {where_sql}",
            tuple(params),
        ).fetchone()
        total = int(total_row["total"]) if total_row is not None else 0
        rows = connection.execute(
            f"""
            SELECT *
            FROM {MESSAGE_TABLE_NAME}
            {where_sql}
            ORDER BY created_ts DESC, id DESC
            """,
            tuple(params),
        ).fetchall()

    return {
        "kind": kind,
        "owner_id": sanitize_owner_id(owner_id),
        "q": str(q or "").strip(),
        "record_kind": normalized_record_kind,
        "actor_role": normalized_actor_role,
        "direction": normalized_direction,
        "message_date": effective_message_date,
        "available_dates": available_dates,
        "items": [_message_payload(row) for row in rows],
        "page": 1,
        "page_size": total,
        "total": total,
    }


async def delete_chat_space(kind: str, owner_id: str) -> dict[str, Any]:
    """删除指定聊天空间的整套聊天目录与消息数据库。

    Args:
        kind: 聊天记录空间类型。
        owner_id: 空间拥有者 ID。

    Returns:
        dict[str, Any]: 删除结果与被清理的目录信息。

    Raises:
        FileNotFoundError: 当聊天记录数据库不存在时抛出。
        ValueError: 当聊天记录空间类型不支持时抛出。
    """

    normalized_owner_id = sanitize_owner_id(owner_id)
    db_path = _existing_chat_db(kind, normalized_owner_id)
    chat_path = db_path.parent.resolve(strict=False)
    root_path = storage_manager.root.resolve(strict=False)
    if not chat_path.is_relative_to(root_path):
        raise ValueError("Chat history path is outside the configured storage root")

    for attempt in range(3):
        try:
            shutil.rmtree(chat_path)
            break
        except PermissionError:
            gc.collect()
            if attempt == 2:
                raise
            await asyncio.sleep(0.05)
    return {
        "deleted": True,
        "kind": kind,
        "owner_id": normalized_owner_id,
        "chat_path": str(chat_path),
        "db_path": str(db_path),
    }
