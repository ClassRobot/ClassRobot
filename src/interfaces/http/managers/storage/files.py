from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from nonebot_plugin_orm import get_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models import Classes, College, Group, GroupBind, School, User
from src.core.storage import DEFAULT_HOME_DIRS, FileSpace, FileSpaceError, PathEscapeError, StorageManager, storage_manager
from src.core.storage.files import SPACE_ROOT_DIRS, normalize_file_space_kind, sanitize_owner_id


def _space_root(kind: str, manager: StorageManager | None = None) -> Path:
    """返回指定文件空间类型对应的根目录。

    Args:
        kind: 文件空间类型，支持 ``user``、``group``、``class``、``college``、``school``。
        manager: 可选的存储管理器实例。

    Returns:
        Path: 该类型文件空间的根目录。

    Raises:
        ValueError: 当文件空间类型不支持时抛出。
    """

    manager = manager or storage_manager
    return manager.root / SPACE_ROOT_DIRS[normalize_file_space_kind(kind)]


def _existing_space(kind: str, owner_id: str, manager: StorageManager | None = None) -> FileSpace:
    """返回已存在的文件空间对象。

    Args:
        kind: 文件空间类型。
        owner_id: 文件空间拥有者标识。
        manager: 可选的存储管理器实例。

    Returns:
        FileSpace: 已存在的文件空间对象。

    Raises:
        FileNotFoundError: 当目标文件空间不存在时抛出。
        ValueError: 当文件空间类型不支持时抛出。
    """

    manager = manager or storage_manager
    normalized_owner_id = sanitize_owner_id(owner_id)
    space_root = _space_root(kind, manager) / normalized_owner_id
    if not space_root.exists() or not space_root.is_dir():
        raise FileNotFoundError(f"File space not found: {kind}/{normalized_owner_id}")
    return FileSpace(kind, normalized_owner_id, manager.root)


def _scan_owner_ids(kind: str, manager: StorageManager | None = None) -> list[str]:
    """扫描磁盘上已存在的文件空间目录名。

    Args:
        kind: 文件空间类型。
        manager: 可选的存储管理器实例。

    Returns:
        list[str]: 已存在空间的拥有者标识列表。
    """

    root = _space_root(kind, manager)
    if not root.exists():
        return []
    return sorted(child.name for child in root.iterdir() if child.is_dir() and not child.name.startswith("."))


def _timestamp_text(timestamp: float | None) -> str | None:
    """把时间戳转换为秒级 ISO 文本。

    Args:
        timestamp: 文件系统时间戳。

    Returns:
        str | None: 转换后的时间文本；空值时返回 ``None``。
    """

    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def _space_stats(home_dir: Path) -> dict[str, Any]:
    """统计文件空间 home 目录的文件、目录和大小信息。

    Args:
        home_dir: 文件空间的 home 目录。

    Returns:
        dict[str, Any]: 文件数、目录数、总大小和最近更新时间。
    """

    file_count = 0
    directory_count = 0
    total_size = 0
    latest_timestamp: float | None = None

    for entry in home_dir.rglob("*"):
        if entry.name.startswith("."):
            continue
        try:
            stat = entry.stat()
        except OSError:
            continue
        latest_timestamp = max(latest_timestamp or 0.0, stat.st_mtime)
        if entry.is_dir():
            directory_count += 1
            continue
        file_count += 1
        total_size += stat.st_size

    return {
        "file_count": file_count,
        "directory_count": directory_count,
        "total_size": total_size,
        "updated_at": _timestamp_text(latest_timestamp),
    }


def _space_owner_payload(
    kind: str,
    owner_id: str,
    user_index: dict[str, User],
    group_index: dict[str, tuple[Group, list[GroupBind]]],
    class_index: dict[str, Classes],
    college_index: dict[str, College],
    school_index: dict[str, School],
) -> dict[str, Any]:
    """根据文件空间所属实体构造展示信息。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。
        user_index: 用户索引。
        group_index: 群组绑定索引。
        class_index: 班级索引。
        college_index: 学院索引。
        school_index: 学校索引。

    Returns:
        dict[str, Any]: 标题、副标题、关联实体和是否成功映射的结果。
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

    if kind == "class":
        classes = class_index.get(owner_id)
        if classes is None:
            return {
                "title": f"班级空间 {owner_id}",
                "subtitle": "未在数据库中找到关联班级",
                "linked": False,
                "owner": None,
            }
        return {
            "title": classes.name,
            "subtitle": f"班级 {classes.id}",
            "linked": True,
            "owner": {
                "type": "class",
                "id": classes.id,
                "name": classes.name,
                "group_id": classes.group_id,
                "school_id": classes.school_id,
                "college_id": classes.college_id,
                "major_id": classes.major_id,
            },
        }

    if kind == "college":
        college = college_index.get(owner_id)
        if college is None:
            return {
                "title": f"学院空间 {owner_id}",
                "subtitle": "未在数据库中找到关联学院",
                "linked": False,
                "owner": None,
            }
        return {
            "title": college.name,
            "subtitle": f"学校 {college.school_id}",
            "linked": True,
            "owner": {
                "type": "college",
                "id": college.id,
                "name": college.name,
                "school_id": college.school_id,
            },
        }

    if kind == "school":
        school = school_index.get(owner_id)
        if school is None:
            return {
                "title": f"学校空间 {owner_id}",
                "subtitle": "未在数据库中找到关联学校",
                "linked": False,
                "owner": None,
            }
        return {
            "title": school.name,
            "subtitle": school.address or f"学校 {school.id}",
            "linked": True,
            "owner": {
                "type": "school",
                "id": school.id,
                "name": school.name,
                "address": school.address,
            },
        }

    group_context = group_index.get(owner_id)
    if group_context is None:
        return {
            "title": f"群空间 {owner_id}",
            "subtitle": "未在数据库中找到关联群组",
            "linked": False,
            "owner": None,
        }

    group, binds = group_context
    classes = getattr(group, "classes", None)
    title = classes.name if isinstance(classes, Classes) else group.name
    platform_ids = sorted({bind.platform_id for bind in binds if bind.platform_id})
    channel_ids = sorted({bind.channel_id for bind in binds if bind.channel_id})
    subtitle_parts = []
    if platform_ids:
        subtitle_parts.append("/".join(platform_ids))
    if channel_ids:
        subtitle_parts.append("、".join(channel_ids))
    subtitle = " · ".join(subtitle_parts) if subtitle_parts else f"系统群组 {group.id}"
    primary_bind = binds[0] if binds else None
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
            "platform_id": primary_bind.platform_id if primary_bind else None,
            "channel_id": primary_bind.channel_id if primary_bind else None,
            "platform_ids": platform_ids,
            "channel_ids": channel_ids,
        },
    }


async def _space_indexes(
    kind: str,
    owner_ids: list[str],
) -> tuple[
    dict[str, User],
    dict[str, tuple[Group, list[GroupBind]]],
    dict[str, Classes],
    dict[str, College],
    dict[str, School],
]:
    """按需批量加载文件空间关联的用户或群组索引。

    Args:
        kind: 文件空间类型。
        owner_ids: 需要映射的拥有者标识列表。

    Returns:
        tuple: 用户、群组、班级、学院、学校索引。
    """

    user_index: dict[str, User] = {}
    group_index: dict[str, tuple[Group, list[GroupBind]]] = {}
    class_index: dict[str, Classes] = {}
    college_index: dict[str, College] = {}
    school_index: dict[str, School] = {}
    if not owner_ids:
        return user_index, group_index, class_index, college_index, school_index

    async with get_session() as session:
        if kind == "user":
            user_ids = [int(owner_id) for owner_id in owner_ids if owner_id.isdigit()]
            if not user_ids:
                return user_index, group_index, class_index, college_index, school_index
            users = await session.scalars(select(User).where(User.id.in_(user_ids)))
            user_index = {str(user.id): user for user in users}
            return user_index, group_index, class_index, college_index, school_index

        entity_ids = [int(owner_id) for owner_id in owner_ids if owner_id.isdigit()]
        if not entity_ids:
            return user_index, group_index, class_index, college_index, school_index

        if kind == "class":
            classes = await session.scalars(select(Classes).where(Classes.id.in_(entity_ids)))
            class_index = {str(classes_item.id): classes_item for classes_item in classes}
            return user_index, group_index, class_index, college_index, school_index

        if kind == "college":
            colleges = await session.scalars(select(College).where(College.id.in_(entity_ids)))
            college_index = {str(college.id): college for college in colleges}
            return user_index, group_index, class_index, college_index, school_index

        if kind == "school":
            schools = await session.scalars(select(School).where(School.id.in_(entity_ids)))
            school_index = {str(school.id): school for school in schools}
            return user_index, group_index, class_index, college_index, school_index

        groups = list(
            await session.scalars(
                select(Group)
                .where(Group.id.in_(entity_ids))
                .options(
                    selectinload(Group.classes),
                    selectinload(Group.creator),
                )
            )
        )
        binds = await session.scalars(
            select(GroupBind)
            .where(GroupBind.group_id.in_(entity_ids))
            .options(
                selectinload(GroupBind.group).selectinload(Group.classes),
                selectinload(GroupBind.group).selectinload(Group.creator),
            )
        )
        binds_by_group: dict[int, list[GroupBind]] = defaultdict(list)
        for bind in binds:
            binds_by_group[bind.group_id].append(bind)
        group_index = {str(group.id): (group, binds_by_group.get(group.id, [])) for group in groups}
    return user_index, group_index, class_index, college_index, school_index


def _space_summary(
    kind: str,
    owner_id: str,
    space: FileSpace,
    owner_payload: dict[str, Any],
) -> dict[str, Any]:
    """构造文件空间列表与详情共用摘要。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。
        space: 文件空间对象。
        owner_payload: 关联实体信息。

    Returns:
        dict[str, Any]: 文件空间摘要数据。
    """

    stats = _space_stats(space.home_dir)
    return {
        "key": f"{kind}:{owner_id}",
        "kind": kind,
        "owner_id": owner_id,
        "title": owner_payload["title"],
        "subtitle": owner_payload["subtitle"],
        "linked": owner_payload["linked"],
        "owner": owner_payload["owner"],
        "cwd": space.pwd(),
        "space_root": str(space.space_root),
        "home_path": str(space.home_dir),
        "chat_path": str(space.chat_dir),
        "default_directories": list(DEFAULT_HOME_DIRS),
        "has_chat_state": space.state_file.exists(),
        **stats,
    }


def _entry_payload(space: FileSpace, display_path: str, name: str, path: Path) -> dict[str, Any]:
    """把真实路径转换为管理端文件条目。

    Args:
        space: 当前文件空间对象。
        display_path: 面向前端展示的 ``~`` 路径。
        name: 显示名称。
        path: 文件系统中的真实路径。

    Returns:
        dict[str, Any]: 文件条目展示数据。
    """

    stat = path.stat()
    return {
        "name": name,
        "path": display_path,
        "is_dir": path.is_dir(),
        "size": 0 if path.is_dir() else stat.st_size,
        "updated_at": _timestamp_text(stat.st_mtime),
        "extension": "" if path.is_dir() else path.suffix.lower(),
    }


def _display_path(space: FileSpace, path: Path) -> str:
    """把真实路径转换为 ``~`` 风格的展示路径。

    Args:
        space: 当前文件空间对象。
        path: 需要转换的真实路径。

    Returns:
        str: 面向前端展示的相对路径。
    """

    relative_parts = tuple(path.resolve(strict=False).relative_to(space.home_dir.resolve()).parts)
    return space.display_path(relative_parts)


def _list_entries(space: FileSpace, path: str | None = None) -> dict[str, Any]:
    """列出文件空间内某一路径下的文件条目。

    Args:
        space: 文件空间对象。
        path: 目标路径，默认为当前工作目录。

    Returns:
        dict[str, Any]: 当前路径、父级路径和条目列表。
    """

    resolved = space.resolve(path, reject_escape=True)
    if not resolved.path.exists():
        raise FileSpaceError(f"路径不存在：{resolved.display}")

    if resolved.path.is_file():
        items = [_entry_payload(space, resolved.display, resolved.path.name, resolved.path)]
    else:
        entries = [item for item in resolved.path.iterdir() if not item.name.startswith(".")]
        entries.sort(key=lambda item: (not item.is_dir(), item.name.lower()))
        items = [_entry_payload(space, _display_path(space, item), item.name, item) for item in entries]

    parent_parts = resolved.relative_parts[:-1] if resolved.relative_parts else tuple()
    return {
        "path": resolved.display,
        "parent_path": space.display_path(parent_parts),
        "can_go_up": bool(resolved.relative_parts),
        "items": items,
        "total": len(items),
    }


async def list_file_spaces(*, kind: str | None = None, q: str | None = None) -> dict[str, Any]:
    """列出磁盘上已存在的用户与群组文件空间。

    Args:
        kind: 可选的文件空间类型过滤条件。
        q: 可选的模糊搜索词。

    Returns:
        dict[str, Any]: 文件空间列表与统计信息。
    """

    kinds = [kind] if kind else ["user", "group", "class", "college", "school"]
    items: list[dict[str, Any]] = []
    keyword = (q or "").strip().lower()

    for current_kind in kinds:
        owner_ids = _scan_owner_ids(current_kind)
        user_index, group_index, class_index, college_index, school_index = await _space_indexes(
            current_kind, owner_ids
        )
        for owner_id in owner_ids:
            space = _existing_space(current_kind, owner_id)
            owner_payload = _space_owner_payload(
                current_kind,
                owner_id,
                user_index,
                group_index,
                class_index,
                college_index,
                school_index,
            )
            item = _space_summary(current_kind, owner_id, space, owner_payload)
            if keyword:
                haystacks = [
                    item["title"],
                    item["subtitle"],
                    item["owner_id"],
                    item["owner"].get("username") if isinstance(item.get("owner"), dict) else "",
                    item["owner"].get("group_name") if isinstance(item.get("owner"), dict) else "",
                    item["owner"].get("class_name") if isinstance(item.get("owner"), dict) else "",
                    item["owner"].get("name") if isinstance(item.get("owner"), dict) else "",
                ]
                if not any(keyword in str(value or "").lower() for value in haystacks):
                    continue
            items.append(item)

    items.sort(key=lambda item: (item.get("updated_at") or "", item["kind"], item["owner_id"]), reverse=True)
    return {
        "items": items,
        "total": len(items),
        "root": str(storage_manager.root),
    }


async def get_file_space_detail(kind: str, owner_id: str) -> dict[str, Any]:
    """读取单个文件空间详情。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。

    Returns:
        dict[str, Any]: 文件空间摘要及当前目录列表。
    """

    space = _existing_space(kind, owner_id)
    user_index, group_index, class_index, college_index, school_index = await _space_indexes(kind, [owner_id])
    owner_payload = _space_owner_payload(
        kind,
        owner_id,
        user_index,
        group_index,
        class_index,
        college_index,
        school_index,
    )
    summary = _space_summary(kind, owner_id, space, owner_payload)
    summary.update(_list_entries(space))
    return summary


async def list_file_space_entries(kind: str, owner_id: str, path: str | None = None) -> dict[str, Any]:
    """列出指定文件空间目录下的条目。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。
        path: 可选的目标路径。

    Returns:
        dict[str, Any]: 目录条目列表。
    """

    space = _existing_space(kind, owner_id)
    return _list_entries(space, path)


async def read_file_space_text(kind: str, owner_id: str, path: str, *, limit: int = 16384) -> dict[str, Any]:
    """读取文件空间中的文本文件内容。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。
        path: 待读取的文件路径。
        limit: 最大读取字节数。

    Returns:
        dict[str, Any]: 文本预览结果。
    """

    space = _existing_space(kind, owner_id)
    display_path, content, truncated = space.read_text(path, limit=limit)
    resolved = space.resolve(path, reject_escape=True)
    stat = resolved.path.stat()
    return {
        "path": display_path,
        "content": content,
        "truncated": truncated,
        "size": stat.st_size,
        "updated_at": _timestamp_text(stat.st_mtime),
        "extension": resolved.path.suffix.lower(),
    }


async def write_file_space_text(kind: str, owner_id: str, path: str, content: str) -> dict[str, Any]:
    """写入或覆盖文件空间中的文本文件。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。
        path: 待写入的目标文件路径。
        content: 新的文本内容。

    Returns:
        dict[str, Any]: 保存结果与文件元数据。
    """

    space = _existing_space(kind, owner_id)
    resolved = space.resolve(path, reject_escape=True)
    if resolved.path.exists() and resolved.path.is_dir():
        raise FileSpaceError(f"目标是目录，不能直接写入文本内容：{resolved.display}")
    if not resolved.path.parent.exists() or not resolved.path.parent.is_dir():
        parent_path = _display_path(space, resolved.path.parent)
        raise FileSpaceError(f"父目录不存在：{parent_path}")
    resolved.path.write_text(content, encoding="utf-8")
    stat = resolved.path.stat()
    return {
        "saved": True,
        "path": resolved.display,
        "size": stat.st_size,
        "updated_at": _timestamp_text(stat.st_mtime),
    }


async def create_file_space_directory(kind: str, owner_id: str, path: str) -> dict[str, Any]:
    """在文件空间中创建目录。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。
        path: 待创建目录路径。

    Returns:
        dict[str, Any]: 创建结果。
    """

    space = _existing_space(kind, owner_id)
    created_path = space.mkdir(path)
    return {"created": True, "path": created_path}


async def delete_file_space_entry(
    kind: str,
    owner_id: str,
    path: str,
    *,
    recursive: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """删除文件空间中的文件或目录。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。
        path: 待删除路径。
        recursive: 是否允许递归删除目录。
        force: 路径不存在时是否静默跳过。

    Returns:
        dict[str, Any]: 删除结果。
    """

    space = _existing_space(kind, owner_id)
    deleted_path = space.remove(path, recursive=recursive, force=force)
    return {"deleted": True, "path": deleted_path}


async def delete_file_space(kind: str, owner_id: str) -> dict[str, Any]:
    """删除整个文件空间根目录。

    Args:
        kind: 文件空间类型。
        owner_id: 拥有者标识。

    Returns:
        dict[str, Any]: 删除结果与被删除的空间路径。

    Raises:
        FileNotFoundError: 当目标文件空间不存在时抛出。
        ValueError: 当文件空间类型不支持时抛出。
        FileSpaceError: 当删除目标超出 storage 根目录时抛出。
    """

    space = _existing_space(kind, owner_id)
    deleted = storage_manager.delete_space(kind, owner_id)
    return {
        "deleted": deleted,
        "kind": kind,
        "owner_id": sanitize_owner_id(owner_id),
        "path": str(space.space_root),
    }
