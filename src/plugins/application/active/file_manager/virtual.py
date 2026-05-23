from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal

from nonebot.adapters import Event
from pydantic import BaseModel, Field

from src.platform.commands import CommandExecutionContext
from src.platform.session.resolvers import resolve_bound_group_id, resolve_or_create_bound_group
from src.models import Classes, College, Group, School, TeacherClasses, User
from src.core.auth import StudentRole
from src.platform.session import BaseSession
from src.core.storage import FileEntry, FileSpace, FileSpaceError, PathEscapeError, StorageManager, storage_manager
from src.core.storage.files import FileSpaceKind, split_path, validate_segment

VIRTUAL_STATE_FILE_NAME = "file_manager_cwd.json"
"""文件管理虚拟工作区的当前目录状态文件名。"""


class MountCategory(StrEnum):
    """文件管理对外展示的挂载分类。"""

    groups = "群组"
    classes = "班级"
    colleges = "学院"
    schools = "学校"


CATEGORY_TITLES: dict[MountCategory, str] = {
    MountCategory.groups: "群组文件",
    MountCategory.classes: "班级文件",
    MountCategory.colleges: "学院文件",
    MountCategory.schools: "学校文件",
}
"""挂载分类展示名称。"""


CATEGORY_SPACE_KIND: dict[MountCategory, FileSpaceKind] = {
    MountCategory.groups: FileSpaceKind.group,
    MountCategory.classes: FileSpaceKind.class_,
    MountCategory.colleges: FileSpaceKind.college,
    MountCategory.schools: FileSpaceKind.school,
}
"""挂载分类对应的物理文件空间类型。"""


RESERVED_MOUNT_NAMES = {category.value for category in MountCategory}
"""个人空间根目录下由虚拟文件系统保留的目录名称。"""


class FileWorkspaceState(BaseModel):
    """记录虚拟文件工作区的当前路径。"""

    parts: tuple[str, ...] = Field(default_factory=tuple)


class FileMount(BaseModel):
    """描述一个挂载到用户文件视图中的外部文件空间。"""

    category: MountCategory
    kind: FileSpaceKind
    owner_id: str
    label: str
    space: FileSpace
    writable: bool = False
    readonly_reason: str | None = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def key(self) -> str:
        """返回用于去重的稳定键。"""

        return f"{self.kind.value}:{self.owner_id}"

    @property
    def path_parts(self) -> tuple[str, str]:
        """返回挂载点在虚拟路径中的片段。"""

        return (self.category.value, self.owner_id)

    @property
    def display_path(self) -> str:
        """返回挂载点展示路径。"""

        return display_path_from_parts(self.path_parts)


class ResolvedWorkspaceTarget(BaseModel):
    """表示虚拟路径解析后的目标。"""

    target_type: Literal["root", "category", "space"]
    display: str
    full_parts: tuple[str, ...] = Field(default_factory=tuple)
    relative_parts: tuple[str, ...] = Field(default_factory=tuple)
    path: Path | None = None
    space: FileSpace | None = None
    mount: FileMount | None = None
    category: MountCategory | None = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def is_physical(self) -> bool:
        """判断当前目标是否映射到真实文件系统路径。"""

        return self.space is not None and self.path is not None


class VirtualFileWorkspace:
    """把用户个人空间和外部授权空间合并成一个虚拟文件视图。

    设计目标是让命令层和 Agent 都只面对一个类似 Linux home 的文件系统：

    - ``~`` 默认是用户自己的个人空间，拥有完整写权限。
    - ``~/群组``、``~/班级``、``~/学院``、``~/学校`` 是虚拟挂载分类。
    - 外部空间默认只读，只有对应管理身份或系统管理员可以写入。
    - 所有路径先在虚拟层处理 ``..``，再交给物理 ``FileSpace`` 二次校验。
    """

    def __init__(
        self,
        *,
        user_id: str | int,
        personal_space: FileSpace,
        mounts: list[FileMount] | None = None,
    ) -> None:
        """初始化虚拟工作区。

        Args:
            user_id: 系统用户 ID。该 ID 只用于定位个人空间和当前目录状态。
            personal_space: 用户个人文件空间。
            mounts: 当前用户可访问的外部挂载空间。
        """

        self.user_id = str(user_id)
        self.personal_space = personal_space
        self.mounts = sorted(mounts or [], key=lambda item: (item.category.value, item.owner_id))
        self.state_file = self.personal_space.chat_dir / VIRTUAL_STATE_FILE_NAME
        self._mount_by_path = {(mount.category.value, mount.owner_id): mount for mount in self.mounts}

    def pwd(self) -> str:
        """返回当前虚拟工作区路径。

        Returns:
            str: 以 ``~`` 开头的当前路径。
        """

        return display_path_from_parts(self.cwd_parts)

    @property
    def cwd_parts(self) -> tuple[str, ...]:
        """读取当前虚拟工作目录。

        Returns:
            tuple[str, ...]: 相对虚拟 ``~`` 的路径片段。
        """

        parts = self._read_state_parts()
        try:
            target = self._target_for_parts(parts)
        except FileSpaceError:
            return tuple()
        if target.target_type in {"root", "category"}:
            return parts
        if target.path and target.path.exists() and target.path.is_dir():
            return parts
        return tuple()

    def cd(self, path: str | None) -> str:
        """切换当前虚拟目录。

        Args:
            path: 用户输入路径。为空时回到 ``~``。

        Returns:
            str: 切换后的展示路径。

        Raises:
            FileSpaceError: 目标不存在或不是目录。
        """

        target = self.resolve(path or "~", clamp_escape=True)
        if target.target_type == "space":
            if not target.path or not target.path.exists():
                raise FileSpaceError(f"目录不存在：{target.display}")
            if not target.path.is_dir():
                raise FileSpaceError(f"目标不是目录：{target.display}")
        self._write_cwd(target.full_parts)
        return target.display

    def list_entries(self, path: str | None = None) -> tuple[str, list[FileEntry]]:
        """列出虚拟路径下的文件和挂载项。

        Args:
            path: 可选路径，默认使用当前虚拟工作目录。

        Returns:
            tuple[str, list[FileEntry]]: 展示路径与条目列表。
        """

        target = self.resolve(path, reject_escape=True)
        if target.target_type == "root":
            return target.display, self._root_entries()
        if target.target_type == "category":
            return target.display, self._category_entries(target.category)
        if not target.path or not target.space:
            raise FileSpaceError(f"路径不存在：{target.display}")
        if not target.path.exists():
            raise FileSpaceError(f"路径不存在：{target.display}")

        _, entries = target.space.list_entries(path_from_parts(target.relative_parts))
        return target.display, [self._decorate_space_entry(target, entry) for entry in entries]

    def mkdir(self, path: str) -> str:
        """创建目录。

        Args:
            path: 待创建目录路径。

        Returns:
            str: 创建后的展示路径。
        """

        target = self.resolve(path, reject_escape=True)
        self._ensure_writable(target)
        created = target.space.mkdir(path_from_parts(target.relative_parts))
        return self._decorate_display(target, created)

    def touch(self, path: str) -> str:
        """创建空文件。

        Args:
            path: 待创建文件路径。

        Returns:
            str: 创建后的展示路径。
        """

        target = self.resolve(path, reject_escape=True)
        self._ensure_writable(target)
        created = target.space.touch(path_from_parts(target.relative_parts))
        return self._decorate_display(target, created)

    def remove(self, path: str, *, recursive: bool = False, force: bool = False) -> str | None:
        """删除文件或目录。

        Args:
            path: 待删除路径。
            recursive: 是否递归删除目录。
            force: 路径不存在时是否静默跳过。

        Returns:
            str | None: 删除成功时的展示路径。
        """

        target = self.resolve(path, reject_escape=True)
        self._ensure_writable(target)
        deleted = target.space.remove(path_from_parts(target.relative_parts), recursive=recursive, force=force)
        if deleted is None:
            return None
        if self._cwd_is_inside(target.full_parts):
            self._write_cwd(tuple())
        return self._decorate_display(target, deleted)

    def read_text(self, path: str, *, limit: int = 4096) -> tuple[str, str, bool]:
        """读取文本文件。

        Args:
            path: 待读取路径。
            limit: 最大读取字节数。

        Returns:
            tuple[str, str, bool]: 展示路径、文本内容、是否截断。
        """

        target = self.resolve(path, reject_escape=True)
        if target.target_type != "space" or not target.space:
            raise FileSpaceError(f"目标不是文件：{target.display}")
        display, text, truncated = target.space.read_text(path_from_parts(target.relative_parts), limit=limit)
        return self._decorate_display(target, display), text, truncated

    def save_bytes(self, filename: str, data: bytes, target_dir: str | None = None) -> str:
        """保存上传文件数据。

        Args:
            filename: 原始文件名。
            data: 文件字节内容。
            target_dir: 可选目标目录。

        Returns:
            str: 保存后的展示路径。
        """

        target = self.resolve(target_dir, reject_escape=True)
        self._ensure_writable(target)
        saved = target.space.save_bytes(filename, data, path_from_parts(target.relative_parts))
        return self._decorate_display(target, saved)

    def save_path(self, filename: str, source: Path, target_dir: str | None = None) -> str:
        """移动本地临时文件到虚拟工作区目标目录。

        Args:
            filename: 原始文件名。
            source: 本地临时文件路径。
            target_dir: 可选目标目录。

        Returns:
            str: 保存后的展示路径。
        """

        target = self.resolve(target_dir, reject_escape=True)
        self._ensure_writable(target)
        saved = target.space.save_path(filename, source, path_from_parts(target.relative_parts))
        return self._decorate_display(target, saved)

    def resolve(
        self,
        path: str | None,
        *,
        clamp_escape: bool = False,
        reject_escape: bool = False,
    ) -> ResolvedWorkspaceTarget:
        """解析虚拟路径。

        Args:
            path: 用户输入路径；为空时使用当前虚拟工作目录。
            clamp_escape: 越界时是否钳制到 ``~``。
            reject_escape: 越界时是否抛错。

        Returns:
            ResolvedWorkspaceTarget: 解析结果。

        Raises:
            PathEscapeError: 路径尝试越过虚拟 ``~``。
            FileSpaceError: 挂载分类或挂载目标不存在。
        """

        parts = self._parse_parts(path, clamp_escape=clamp_escape, reject_escape=reject_escape)
        return self._target_for_parts(parts)

    def search_targets(self, path: str | None = None) -> tuple[str, list[ResolvedWorkspaceTarget]]:
        """返回某个虚拟路径覆盖到的可读物理搜索根。

        Args:
            path: 可选搜索路径。

        Returns:
            tuple[str, list[ResolvedWorkspaceTarget]]: 展示路径与物理搜索目标列表。

        Raises:
            FileSpaceError: 搜索路径不存在。
        """

        target = self.resolve(path, reject_escape=True)
        if target.target_type == "root":
            roots = [self._personal_root_target()]
            roots.extend(self._mount_root_target(mount) for mount in self.mounts)
            return target.display, roots
        if target.target_type == "category":
            roots = [self._mount_root_target(mount) for mount in self._mounts_for_category(target.category)]
            return target.display, roots
        if not target.path or not target.path.exists():
            raise FileSpaceError(f"路径不存在：{target.display}")
        return target.display, [target]

    def _read_state_parts(self) -> tuple[str, ...]:
        """从状态文件读取虚拟路径片段。"""

        if self.state_file.exists():
            try:
                state = FileWorkspaceState.parse_obj(json.loads(self.state_file.read_text(encoding="utf-8")))
                return tuple(state.parts)
            except (OSError, ValueError, TypeError):
                return tuple()
        return self.personal_space.cwd_parts

    def _write_cwd(self, parts: tuple[str, ...]) -> None:
        """写入当前虚拟目录状态。"""

        self.personal_space.chat_dir.mkdir(parents=True, exist_ok=True)
        state = FileWorkspaceState(parts=parts)
        self.state_file.write_text(state.json(ensure_ascii=False), encoding="utf-8")

    def _parse_parts(self, path: str | None, *, clamp_escape: bool, reject_escape: bool) -> tuple[str, ...]:
        """把用户输入路径拆解为虚拟路径片段。"""

        raw_path = "" if path is None else str(path).strip()
        if not raw_path:
            return self.cwd_parts

        is_rooted = raw_path.startswith(("~", "/", "\\"))
        raw_path = raw_path[1:] if raw_path.startswith("~") else raw_path
        raw_path = raw_path.lstrip("/\\") if is_rooted else raw_path
        parts = [] if is_rooted else list(self.cwd_parts)
        escaped = False

        for segment in split_path(raw_path):
            validate_segment(segment)
            if segment == ".":
                continue
            if segment == "..":
                if parts:
                    parts.pop()
                else:
                    escaped = True
                continue
            parts.append(segment)

        if escaped and reject_escape:
            raise PathEscapeError("路径不能越过当前文件空间根目录。")
        if escaped and clamp_escape:
            return tuple()
        return tuple(parts)

    def _target_for_parts(self, parts: tuple[str, ...]) -> ResolvedWorkspaceTarget:
        """把虚拟路径片段映射为根、分类或物理空间。"""

        if not parts:
            return ResolvedWorkspaceTarget(target_type="root", display="~")

        first = parts[0]
        if first in RESERVED_MOUNT_NAMES:
            category = MountCategory(first)
            if len(parts) == 1:
                return ResolvedWorkspaceTarget(
                    target_type="category",
                    display=display_path_from_parts(parts),
                    full_parts=parts,
                    category=category,
                )

            owner_id = parts[1]
            mount = self._mount_by_path.get((first, owner_id))
            if mount is None:
                raise FileSpaceError(f"当前没有可访问的挂载空间：{first}/{owner_id}")
            relative_parts = tuple(parts[2:])
            resolved = mount.space.resolve(path_from_parts(relative_parts), base_parts=tuple(), reject_escape=True)
            return ResolvedWorkspaceTarget(
                target_type="space",
                display=display_path_from_parts(parts),
                full_parts=parts,
                relative_parts=resolved.relative_parts,
                path=resolved.path,
                space=mount.space,
                mount=mount,
                category=mount.category,
            )

        resolved = self.personal_space.resolve(path_from_parts(parts), base_parts=tuple(), reject_escape=True)
        return ResolvedWorkspaceTarget(
            target_type="space",
            display=display_path_from_parts(parts),
            full_parts=parts,
            relative_parts=resolved.relative_parts,
            path=resolved.path,
            space=self.personal_space,
        )

    def _root_entries(self) -> list[FileEntry]:
        """构造 ``~`` 下的个人文件与挂载分类条目。"""

        entries: list[FileEntry] = []
        for category in MountCategory:
            if self._mounts_for_category(category):
                entries.append(
                    FileEntry(
                        name=f"{category.value}/",
                        path=display_path_from_parts((category.value,)),
                        is_dir=True,
                        is_mount=True,
                        readonly=True,
                        title=CATEGORY_TITLES[category],
                        kind="mount_category",
                    )
                )

        _, personal_entries = self.personal_space.list_entries("~")
        for entry in personal_entries:
            if entry.name.rstrip("/") in RESERVED_MOUNT_NAMES:
                continue
            entries.append(entry)
        return entries

    def _category_entries(self, category: MountCategory | None) -> list[FileEntry]:
        """构造某个挂载分类下的具体挂载项。"""

        if category is None:
            return []
        return [
            FileEntry(
                name=f"{mount.owner_id}/",
                path=mount.display_path,
                is_dir=True,
                is_mount=True,
                readonly=not mount.writable,
                title=mount.label,
                kind=mount.kind.value,
            )
            for mount in self._mounts_for_category(category)
        ]

    def _mounts_for_category(self, category: MountCategory | None) -> list[FileMount]:
        """返回指定分类下的挂载列表。"""

        if category is None:
            return []
        return [mount for mount in self.mounts if mount.category == category]

    def _personal_root_target(self) -> ResolvedWorkspaceTarget:
        """返回个人空间根目录搜索目标。"""

        resolved = self.personal_space.resolve("~", base_parts=tuple(), reject_escape=True)
        return ResolvedWorkspaceTarget(
            target_type="space",
            display="~",
            full_parts=tuple(),
            relative_parts=tuple(),
            path=resolved.path,
            space=self.personal_space,
        )

    def _mount_root_target(self, mount: FileMount) -> ResolvedWorkspaceTarget:
        """返回挂载空间根目录搜索目标。"""

        resolved = mount.space.resolve("~", base_parts=tuple(), reject_escape=True)
        return ResolvedWorkspaceTarget(
            target_type="space",
            display=mount.display_path,
            full_parts=mount.path_parts,
            relative_parts=tuple(),
            path=resolved.path,
            space=mount.space,
            mount=mount,
            category=mount.category,
        )

    def _decorate_space_entry(self, target: ResolvedWorkspaceTarget, entry: FileEntry) -> FileEntry:
        """把物理空间条目转换成虚拟路径条目。"""

        if target.mount is None:
            return entry
        relative_parts = display_to_parts(entry.path)
        return FileEntry(
            **{
                **entry.dict(),
                "path": display_path_from_parts((*target.mount.path_parts, *relative_parts)),
                "readonly": not target.mount.writable,
                "kind": entry.kind or target.mount.kind.value,
            }
        )

    def _decorate_display(self, target: ResolvedWorkspaceTarget, display: str) -> str:
        """把物理 ``~`` 路径转换成虚拟展示路径。"""

        if target.mount is None:
            return display
        return display_path_from_parts((*target.mount.path_parts, *display_to_parts(display)))

    def _ensure_writable(self, target: ResolvedWorkspaceTarget) -> None:
        """校验目标是否允许写入。"""

        if target.target_type == "category" and target.category is not None:
            raise FileSpaceError(f"`{target.category.value}` 是文件管理挂载系统保留目录名，不能创建同名目录。")
        if target.target_type != "space" or target.space is None:
            raise FileSpaceError("不能在虚拟挂载目录本身执行写入操作。")
        if target.mount is not None and not target.mount.writable:
            reason = target.mount.readonly_reason or "当前身份只允许查询该空间。"
            raise FileSpaceError(f"没有写入权限：{target.mount.label}。{reason}")
        if target.mount is None and target.relative_parts[:1] and target.relative_parts[0] in RESERVED_MOUNT_NAMES:
            raise FileSpaceError("该目录名已被文件管理挂载系统保留，不能在个人根目录下创建同名目录。")

    def _cwd_is_inside(self, deleted_parts: tuple[str, ...]) -> bool:
        """判断当前虚拟目录是否位于被删除路径之下。"""

        if not deleted_parts:
            return True
        current = self.cwd_parts
        return current[: len(deleted_parts)] == deleted_parts


async def build_event_file_workspace(
    platform: BaseSession,
    user: User,
    event: Event | None = None,
    manager: StorageManager | None = None,
) -> VirtualFileWorkspace:
    """根据消息事件构建文件管理虚拟工作区。

    Args:
        platform: 当前消息会话信息。
        user: 当前系统用户。
        event: 可选原始事件；群聊首次出现时用于自动创建系统群组。
        manager: 可选存储管理器。

    Returns:
        VirtualFileWorkspace: 当前用户的虚拟文件工作区。
    """

    manager = manager or storage_manager
    current_group_id: int | None = None
    if platform.is_group:
        current_group_id = await resolve_platform_group_id(platform, event)
    return await build_user_file_workspace(
        user_id=user.id,
        user=user,
        manager=manager,
        current_group_id=current_group_id,
    )


async def build_context_file_workspace(
    context: CommandExecutionContext,
    manager: StorageManager | None = None,
) -> VirtualFileWorkspace:
    """根据统一命令上下文构建文件管理虚拟工作区。

    Args:
        context: Agent 或系统调用命令时传入的上下文。
        manager: 可选存储管理器。

    Returns:
        VirtualFileWorkspace: 当前上下文可访问的虚拟文件工作区。

    Raises:
        FileSpaceError: 上下文缺少用户 ID。
    """

    manager = manager or storage_manager
    if context.user_id is None:
        raise FileSpaceError("缺少用户 ID，无法定位个人文件空间。")

    user = await User.filter(id=context.user_id).first()
    current_group_id = resolve_context_group_space_id(context)
    if current_group_id is None and context.channel_id and context.platform:
        current_group_id = await resolve_bound_group_id(
            BaseSession(
                user_id=str(context.user_id or ""),
                platform=context.platform,
                platform_name=str(context.extra.get("platform_name") or ""),
                channel_id=context.channel_id,
                guild_id=context.guild_id,
            )
        )
    return await build_user_file_workspace(
        user_id=context.user_id,
        user=user,
        manager=manager,
        current_group_id=current_group_id,
    )


async def build_user_file_workspace(
    *,
    user_id: str | int,
    user: User | None,
    manager: StorageManager | None = None,
    current_group_id: str | int | None = None,
) -> VirtualFileWorkspace:
    """构建指定系统用户的虚拟文件工作区。

    Args:
        user_id: 系统用户 ID。
        user: 可选用户模型。缺失时只暴露个人空间。
        manager: 可选存储管理器。
        current_group_id: 当前消息上下文中的系统群组 ID。

    Returns:
        VirtualFileWorkspace: 可用于命令执行的工作区。
    """

    manager = manager or storage_manager
    personal_space = manager.user_space(user_id)
    mounts: dict[str, FileMount] = {}

    if user is not None:
        user = await User.filter(id=user.id).first() or user
        for group in await Group.filter(creator_id=user.id).all():
            _add_mount(mounts, await _group_mount(group, user, manager))

        if user.student is not None:
            classes = await Classes.filter(id=user.student.classes_id).first()
            if classes is not None:
                await _add_class_hierarchy_mounts(mounts, classes, user, manager)

        if user.teacher is not None:
            teacher_classes = await TeacherClasses.filter(teacher_id=user.teacher.id).all()
            for relation in teacher_classes:
                classes = await Classes.filter(id=relation.classes_id).first()
                if classes is not None:
                    await _add_class_hierarchy_mounts(mounts, classes, user, manager)
            if user.teacher.college_id is not None:
                college = await College.filter(id=user.teacher.college_id).first()
                if college is not None:
                    _add_mount(mounts, _college_mount(college, user, manager))
            if user.teacher.school_id is not None:
                school = await School.filter(id=user.teacher.school_id).first()
                if school is not None:
                    _add_mount(mounts, _school_mount(school, user, manager))

    if current_group_id is not None:
        group = await Group.filter(id=int(current_group_id)).first() if str(current_group_id).isdigit() else None
        if group is not None:
            _add_mount(mounts, await _group_mount(group, user, manager))

    return VirtualFileWorkspace(
        user_id=user_id,
        personal_space=personal_space,
        mounts=list(mounts.values()),
    )


async def resolve_platform_group_id(platform: BaseSession, event: Event | None = None) -> int:
    """把平台群聊上下文解析为系统群组主键。

    Args:
        platform: 当前消息会话信息。
        event: 可选原始事件；群组尚未绑定时用于自动创建系统群组。

    Returns:
        int: 系统内 ``Group.id``。

    Raises:
        FileSpaceError: 当前会话不是有效群聊或无法解析系统群组。
    """

    if not platform.is_group or platform.channel_id is None:
        raise FileSpaceError("当前上下文不是可用的群组会话。")

    if group_id := await resolve_bound_group_id(platform):
        return group_id

    if event is None:
        raise FileSpaceError("当前群聊尚未绑定系统群组，无法定位群文件空间。")

    group = await resolve_or_create_bound_group(platform, event)
    if group is None:
        raise FileSpaceError("当前群聊尚未绑定系统群组，无法定位群文件空间。")
    return group.id


def resolve_context_group_space_id(context: CommandExecutionContext) -> int | None:
    """从统一命令上下文中读取已知的系统群组主键。

    Args:
        context: 统一命令执行上下文。

    Returns:
        int | None: 系统群组主键；缺失或无法转换时返回 ``None``。
    """

    for key in ("group_id", "system_group_id"):
        value = context.extra.get(key)
        if value not in (None, "") and str(value).isdigit():
            return int(value)
    if context.channel_id and not context.platform and str(context.channel_id).isdigit():
        return int(context.channel_id)
    return None


async def _add_class_hierarchy_mounts(
    mounts: dict[str, FileMount],
    classes: Classes,
    user: User,
    manager: StorageManager,
) -> None:
    """把班级及其上级学院、学校加入挂载集合。"""

    _add_mount(mounts, await _class_mount(classes, user, manager))
    if classes.college_id is not None:
        college = await College.filter(id=classes.college_id).first()
        if college is not None:
            _add_mount(mounts, _college_mount(college, user, manager))
    if classes.school_id is not None:
        school = await School.filter(id=classes.school_id).first()
        if school is not None:
            _add_mount(mounts, _school_mount(school, user, manager))


async def _group_mount(group: Group, user: User | None, manager: StorageManager) -> FileMount:
    """创建群组挂载。"""

    writable = bool(user and await can_write_group_space(user, group))
    return FileMount(
        category=MountCategory.groups,
        kind=FileSpaceKind.group,
        owner_id=str(group.id),
        label=group.name,
        space=manager.group_space(group.id),
        writable=writable,
        readonly_reason=None if writable else "只有群组创建者、班级教师或管理员可以修改群组文件。",
    )


async def _class_mount(classes: Classes, user: User, manager: StorageManager) -> FileMount:
    """创建班级挂载。"""

    writable = await can_write_class_space(user, classes)
    return FileMount(
        category=MountCategory.classes,
        kind=FileSpaceKind.class_,
        owner_id=str(classes.id),
        label=classes.name,
        space=manager.class_space(classes.id),
        writable=writable,
        readonly_reason=None if writable else "只有班级教师、班干部、班级创建者或管理员可以修改班级文件。",
    )


def _college_mount(college: College, user: User, manager: StorageManager) -> FileMount:
    """创建学院挂载。"""

    writable = bool(user.is_admin)
    return FileMount(
        category=MountCategory.colleges,
        kind=FileSpaceKind.college,
        owner_id=str(college.id),
        label=college.name,
        space=manager.college_space(college.id),
        writable=writable,
        readonly_reason=None if writable else "学院文件当前仅系统管理员可以修改。",
    )


def _school_mount(school: School, user: User, manager: StorageManager) -> FileMount:
    """创建学校挂载。"""

    writable = bool(user.is_admin)
    return FileMount(
        category=MountCategory.schools,
        kind=FileSpaceKind.school,
        owner_id=str(school.id),
        label=school.name,
        space=manager.school_space(school.id),
        writable=writable,
        readonly_reason=None if writable else "学校文件当前仅系统管理员可以修改。",
    )


def _add_mount(mounts: dict[str, FileMount], mount: FileMount) -> None:
    """按稳定键加入挂载，避免同一空间重复出现。"""

    existing = mounts.get(mount.key)
    if existing is None or (mount.writable and not existing.writable):
        mounts[mount.key] = mount


async def can_write_group_space(user: User, group: Group) -> bool:
    """判断用户是否可以修改群组文件空间。"""

    if user.is_admin or group.creator_id == user.id:
        return True
    classes = await Classes.filter(group_id=group.id).first()
    return bool(classes and await can_write_class_space(user, classes))


async def can_write_class_space(user: User, classes: Classes) -> bool:
    """判断用户是否可以修改班级文件空间。"""

    if user.is_admin:
        return True
    group = await Group.filter(id=classes.group_id).first()
    if group is not None and group.creator_id == user.id:
        return True
    if (
        user.teacher is not None
        and await TeacherClasses.filter(
            teacher_id=user.teacher.id,
            classes_id=classes.id,
        ).exists()
    ):
        return True
    return bool(user.student and user.student.classes_id == classes.id and user.student.role != StudentRole.student)


def display_path_from_parts(parts: tuple[str, ...]) -> str:
    """把虚拟路径片段渲染为 ``~`` 路径。"""

    return "~" if not parts else "~/" + "/".join(parts)


def display_to_parts(display: str) -> tuple[str, ...]:
    """把 ``~`` 展示路径拆回相对路径片段。"""

    text = str(display or "").strip()
    if not text or text == "~":
        return tuple()
    if text.startswith("~/"):
        text = text[2:]
    elif text.startswith("~"):
        text = text[1:].lstrip("/\\")
    return tuple(split_path(text))


def path_from_parts(parts: tuple[str, ...]) -> str:
    """把相对路径片段转换成 ``FileSpace`` 可接受的路径字符串。"""

    return "~" if not parts else "/".join(parts)
