from __future__ import annotations

import re
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from utils.config import storage_dir

FileSpaceKind = Literal["user", "group"]
DEFAULT_HOME_DIRS = ("documents", "videos", "images", "audio")
STATE_FILE_NAME = "cwd.json"
WINDOWS_INVALID_CHARS = set('<>:"|?*')


class FileSpaceError(ValueError):
    """表示文件空间操作失败。"""


class PathEscapeError(FileSpaceError):
    """表示用户输入路径尝试越过当前文件空间根目录。"""


@dataclass(frozen=True)
class ResolvedPath:
    """表示一次路径解析结果。"""

    path: Path
    relative_parts: tuple[str, ...]
    escaped: bool = False

    @property
    def display(self) -> str:
        """返回面向用户展示的 ``~`` 路径。"""

        if not self.relative_parts:
            return "~"
        return "~/" + "/".join(self.relative_parts)


@dataclass(frozen=True)
class FileEntry:
    """表示文件列表中的一个条目。"""

    name: str
    path: str
    is_dir: bool
    size: int | None = None


class FileSpace:
    """表示一个用户或群组的隔离文件空间。

    每个文件空间都有独立的 ``chat`` 和 ``home`` 目录。命令层只能访问
    ``home`` 目录，并把它展示为 ``~``；``chat`` 目录用于保存会话记录、
    当前工作目录等运行时状态。
    """

    def __init__(self, kind: FileSpaceKind, owner_id: str | int, root: Path = storage_dir) -> None:
        """初始化文件空间。

        Args:
            kind: 文件空间类型，``user`` 表示个人空间，``group`` 表示群空间。
            owner_id: 用户或群组的唯一 ID。
            root: storage 根目录，默认来自 ``utils.config.storage_dir``。
        """

        self.kind = kind
        self.owner_id = sanitize_owner_id(owner_id)
        self.root = Path(root)
        self.space_root = self.root / ("users" if kind == "user" else "groups") / self.owner_id
        self.chat_dir = self.space_root / "chat"
        self.home_dir = self.space_root / "home"
        self.state_file = self.chat_dir / STATE_FILE_NAME
        self.ensure_ready()

    def ensure_ready(self) -> None:
        """确保当前文件空间的基础目录已经存在。"""

        self.chat_dir.mkdir(parents=True, exist_ok=True)
        self.home_dir.mkdir(parents=True, exist_ok=True)
        for dirname in DEFAULT_HOME_DIRS:
            (self.home_dir / dirname).mkdir(parents=True, exist_ok=True)

    def pwd(self) -> str:
        """返回当前工作目录的展示路径。

        Returns:
            str: 以 ``~`` 开头的当前目录。
        """

        return self.display_path(self.cwd_parts)

    @property
    def cwd_parts(self) -> tuple[str, ...]:
        """读取当前工作目录。

        Returns:
            tuple[str, ...]: 相对 ``home`` 的路径片段。状态文件损坏或目录不存在时返回根目录。
        """

        if not self.state_file.exists():
            return tuple()
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return tuple()
        raw_path = str(payload.get("cwd") or "")
        resolved = self.resolve(raw_path, base_parts=tuple(), clamp_escape=True)
        if resolved.path.is_dir():
            return resolved.relative_parts
        return tuple()

    def cd(self, path: str | None) -> str:
        """切换当前工作目录。

        ``cd ..`` 在根目录会被固定在 ``~``，不会越过当前用户或群组空间。

        Args:
            path: 用户输入的目标目录。

        Returns:
            str: 切换后的展示路径。

        Raises:
            FileSpaceError: 目标不存在或不是目录。
        """

        resolved = self.resolve(path or "~", clamp_escape=True)
        if not resolved.path.exists():
            raise FileSpaceError(f"目录不存在：{resolved.display}")
        if not resolved.path.is_dir():
            raise FileSpaceError(f"目标不是目录：{resolved.display}")
        self._write_cwd(resolved.relative_parts)
        return resolved.display

    def list_entries(self, path: str | None = None, *, include_size: bool = False) -> tuple[str, list[FileEntry]]:
        """列出目录内容或查看单个文件信息。

        Args:
            path: 可选路径，默认使用当前工作目录。
            include_size: 是否额外统计条目大小。默认关闭，避免 ``ls`` 场景产生多余性能开销。

        Returns:
            tuple[str, list[FileEntry]]: 展示路径和目录条目列表。

        Raises:
            FileSpaceError: 路径不存在。
            PathEscapeError: 路径尝试越界。
        """

        resolved = self.resolve(path, reject_escape=True)
        if not resolved.path.exists():
            raise FileSpaceError(f"路径不存在：{resolved.display}")
        if resolved.path.is_file():
            return resolved.display, [self._entry_for(resolved.path, include_size=include_size)]
        entries = [
            self._entry_for(item, include_size=include_size)
            for item in resolved.path.iterdir()
            if not item.name.startswith(".")
        ]
        entries.sort(key=lambda item: (not item.is_dir, item.name.lower()))
        return resolved.display, entries

    def mkdir(self, path: str) -> str:
        """创建目录。

        Args:
            path: 待创建目录路径。

        Returns:
            str: 创建目录的展示路径。

        Raises:
            FileSpaceError: 目录已存在或父路径不是目录。
            PathEscapeError: 路径尝试越界。
        """

        resolved = self.resolve(path, reject_escape=True)
        if resolved.path.exists():
            raise FileSpaceError(f"路径已存在：{resolved.display}")
        parent = resolved.path.parent
        if not parent.exists() or not parent.is_dir():
            raise FileSpaceError(f"父目录不存在：{self.display_path(self._relative_parts(parent))}")
        resolved.path.mkdir()
        return resolved.display

    def touch(self, path: str) -> str:
        """创建空文件。

        已存在的文件不会被修改，这样可以避免 ``touch`` 意外改变用户数据。

        Args:
            path: 待创建文件路径。

        Returns:
            str: 创建文件的展示路径。

        Raises:
            FileSpaceError: 文件已存在或父路径不可写。
            PathEscapeError: 路径尝试越界。
        """

        resolved = self.resolve(path, reject_escape=True)
        if resolved.path.exists():
            raise FileSpaceError(f"路径已存在：{resolved.display}")
        if not resolved.path.parent.exists() or not resolved.path.parent.is_dir():
            raise FileSpaceError(f"父目录不存在：{self.display_path(self._relative_parts(resolved.path.parent))}")
        resolved.path.write_bytes(b"")
        return resolved.display

    def remove(self, path: str, *, recursive: bool = False, force: bool = False) -> str | None:
        """删除文件或目录。

        Args:
            path: 待删除路径。
            recursive: 是否递归删除目录。
            force: 路径不存在时是否静默跳过。

        Returns:
            str | None: 删除成功时返回展示路径；被 ``force`` 跳过时返回 ``None``。

        Raises:
            FileSpaceError: 删除目标不存在、受保护或目录需要递归删除。
            PathEscapeError: 路径尝试越界。
        """

        resolved = self.resolve(path, reject_escape=True)
        if not resolved.path.exists():
            if force:
                return None
            raise FileSpaceError(f"路径不存在：{resolved.display}")
        self._ensure_removable(resolved)
        if resolved.path.is_dir() and not resolved.path.is_symlink():
            if not recursive:
                raise FileSpaceError(f"目标是目录，请使用 rm -r 删除：{resolved.display}")
            shutil.rmtree(resolved.path)
        else:
            resolved.path.unlink()
        if tuple(self.cwd_parts[: len(resolved.relative_parts)]) == resolved.relative_parts:
            self._write_cwd(tuple())
        return resolved.display

    def read_text(self, path: str, *, limit: int = 4096) -> tuple[str, str, bool]:
        """读取文本文件内容。

        Args:
            path: 待读取文件路径。
            limit: 最多读取的字节数。

        Returns:
            tuple[str, str, bool]: 展示路径、文本内容、是否被截断。

        Raises:
            FileSpaceError: 路径不存在、目标不是文件或无法按文本解码。
            PathEscapeError: 路径尝试越界。
        """

        resolved = self.resolve(path, reject_escape=True)
        if not resolved.path.exists():
            raise FileSpaceError(f"路径不存在：{resolved.display}")
        if not resolved.path.is_file():
            raise FileSpaceError(f"目标不是文件：{resolved.display}")
        size = resolved.path.stat().st_size
        data = resolved.path.read_bytes()[:limit]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise FileSpaceError("暂不支持直接查看二进制文件。") from error
        return resolved.display, text, size > limit

    def save_bytes(self, filename: str, data: bytes, target_dir: str | None = None) -> str:
        """保存上传文件数据。

        Args:
            filename: 原始文件名。
            data: 文件字节内容。
            target_dir: 可选目标目录，默认使用当前工作目录。

        Returns:
            str: 保存后的展示路径。

        Raises:
            FileSpaceError: 目标目录不存在或不是目录。
            PathEscapeError: 目标目录尝试越界。
        """

        safe_name = sanitize_filename(filename)
        target = self.resolve(target_dir, reject_escape=True)
        if not target.path.exists():
            raise FileSpaceError(f"目标目录不存在：{target.display}")
        if not target.path.is_dir():
            raise FileSpaceError(f"目标不是目录：{target.display}")
        file_path = unique_child_path(target.path, safe_name)
        file_path.write_bytes(data)
        return self.display_path(self._relative_parts(file_path))

    def save_path(self, filename: str, source: Path, target_dir: str | None = None) -> str:
        """移动本地临时文件到当前文件空间。

        Args:
            filename: 原始文件名。
            source: 本地临时文件路径。
            target_dir: 可选目标目录，默认使用当前工作目录。

        Returns:
            str: 保存后的展示路径。
        """

        safe_name = sanitize_filename(filename)
        target = self.resolve(target_dir, reject_escape=True)
        if not target.path.exists() or not target.path.is_dir():
            raise FileSpaceError(f"目标目录不存在或不是目录：{target.display}")
        file_path = unique_child_path(target.path, safe_name)
        shutil.move(str(source), file_path)
        return self.display_path(self._relative_parts(file_path))

    def resolve(
        self,
        path: str | None,
        *,
        base_parts: tuple[str, ...] | None = None,
        clamp_escape: bool = False,
        reject_escape: bool = False,
    ) -> ResolvedPath:
        """把用户输入路径解析到当前 ``home`` 内的安全路径。

        Args:
            path: 用户输入路径；为空时使用当前工作目录。
            base_parts: 自定义基准目录片段，默认使用当前工作目录。
            clamp_escape: 为 ``True`` 时越界会被钳制在 ``~``。
            reject_escape: 为 ``True`` 时越界会抛出 ``PathEscapeError``。

        Returns:
            ResolvedPath: 安全解析后的路径信息。

        Raises:
            FileSpaceError: 路径片段包含非法字符。
            PathEscapeError: 路径尝试越界且 ``reject_escape`` 为 ``True``。
        """

        raw_path = "" if path is None else str(path).strip()
        if not raw_path:
            parts = list(base_parts if base_parts is not None else self.cwd_parts)
            return self._resolved(parts, escaped=False)

        is_rooted = raw_path.startswith(("~", "/", "\\"))
        raw_path = raw_path[1:] if raw_path.startswith("~") else raw_path
        raw_path = raw_path.lstrip("/\\") if is_rooted else raw_path
        parts = [] if is_rooted else list(base_parts if base_parts is not None else self.cwd_parts)
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
            parts = []
        return self._resolved(parts, escaped=escaped)

    def display_path(self, parts: tuple[str, ...]) -> str:
        """把相对路径片段渲染为 ``~`` 路径。"""

        return "~" if not parts else "~/" + "/".join(parts)

    def _resolved(self, parts: list[str], *, escaped: bool) -> ResolvedPath:
        """构建并校验解析结果。"""

        candidate = self.home_dir.joinpath(*parts)
        home = self.home_dir.resolve()
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(home):
            raise PathEscapeError("路径不能越过当前文件空间根目录。")
        return ResolvedPath(path=resolved, relative_parts=tuple(parts), escaped=escaped)

    def _relative_parts(self, path: Path) -> tuple[str, ...]:
        """返回路径相对 ``home`` 的片段。"""

        return tuple(path.resolve(strict=False).relative_to(self.home_dir.resolve()).parts)

    def _entry_for(self, path: Path, *, include_size: bool = False) -> FileEntry:
        """把真实路径转换为展示条目。"""

        relative_parts = self._relative_parts(path)
        is_dir = path.is_dir()
        size = None
        if include_size:
            size = directory_size(path) if is_dir else path.stat().st_size
        return FileEntry(
            name=path.name + ("/" if is_dir else ""),
            path=self.display_path(relative_parts),
            is_dir=is_dir,
            size=size,
        )

    def _ensure_removable(self, resolved: ResolvedPath) -> None:
        """校验删除目标是否允许被删除。"""

        if not resolved.relative_parts:
            raise FileSpaceError("不能删除当前文件空间根目录。")
        if len(resolved.relative_parts) == 1 and resolved.relative_parts[0] in DEFAULT_HOME_DIRS:
            raise FileSpaceError(f"不能删除默认目录：{resolved.display}")

    def _write_cwd(self, parts: tuple[str, ...]) -> None:
        """写入当前工作目录状态。"""

        self.chat_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps({"cwd": "/".join(parts)}, ensure_ascii=False), encoding="utf-8")


class StorageManager:
    """管理系统级 storage 根目录和各用户文件空间。"""

    def __init__(self, root: Path = storage_dir) -> None:
        """初始化存储管理器。

        Args:
            root: storage 根目录。
        """

        self.root = Path(root)
        self.ensure_root()

    def ensure_root(self) -> None:
        """确保 storage 根目录和一级目录存在。"""

        for dirname in ("public", "groups", "users"):
            (self.root / dirname).mkdir(parents=True, exist_ok=True)

    def space_root(self, kind: FileSpaceKind, owner_id: str | int) -> Path:
        """返回指定文件空间的根目录路径。

        Args:
            kind: 文件空间类型，``user`` 或 ``group``。
            owner_id: 用户或群组唯一 ID。

        Returns:
            Path: 对应文件空间的根目录。
        """

        sanitized_owner_id = sanitize_owner_id(owner_id)
        dirname = "users" if kind == "user" else "groups"
        return self.root / dirname / sanitized_owner_id

    def user_space(self, user_id: str | int) -> FileSpace:
        """返回个人文件空间。"""

        return FileSpace("user", user_id, self.root)

    def group_space(self, group_id: str | int) -> FileSpace:
        """返回群组文件空间。"""

        return FileSpace("group", group_id, self.root)

    def delete_space(self, kind: FileSpaceKind, owner_id: str | int) -> bool:
        """删除整个文件空间。

        该操作会直接清理 ``space_root`` 下的全部内容，包括 ``chat``、
        ``home`` 以及后续扩展出来的任意子目录。方法本身是幂等的：
        目标不存在时返回 ``False``，不会抛错。

        Args:
            kind: 文件空间类型，``user`` 或 ``group``。
            owner_id: 用户或群组唯一 ID。

        Returns:
            bool: 实际删除了目录时返回 ``True``，目录原本不存在时返回 ``False``。

        Raises:
            FileSpaceError: 计算出的删除目标不在 storage 根目录下。
            OSError: 文件系统删除失败时抛出原始异常。
        """

        space_root = self.space_root(kind, owner_id)
        if not space_root.exists():
            return False

        root_path = self.root.resolve(strict=False)
        target_path = space_root.resolve(strict=False)
        if not target_path.is_relative_to(root_path):
            raise FileSpaceError("文件空间删除目标超出了 storage 根目录。")

        shutil.rmtree(target_path)
        return True

    def delete_user_space(self, user_id: str | int) -> bool:
        """删除指定用户的整个文件空间。"""

        return self.delete_space("user", user_id)

    def delete_group_space(self, group_id: str | int) -> bool:
        """删除指定群组的整个文件空间。"""

        return self.delete_space("group", group_id)


def sanitize_owner_id(value: str | int) -> str:
    """把用户或群组 ID 转换为安全目录名。"""

    text = str(value).strip()
    if not text:
        raise FileSpaceError("文件空间 ID 不能为空。")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)


def sanitize_filename(value: str | None) -> str:
    """清理上传文件名，避免路径分隔符和 Windows 非法字符。"""

    text = Path(str(value or "file")).name.strip() or "file"
    sanitized = "".join("_" if char in WINDOWS_INVALID_CHARS or char in {"/", "\\"} else char for char in text)
    return sanitized.strip(". ") or "file"


def split_path(path: str) -> list[str]:
    """拆分兼容 ``/`` 与 ``\\`` 的用户输入路径。"""

    return [segment for segment in re.split(r"[\\/]+", path) if segment]


def validate_segment(segment: str) -> None:
    """校验单个路径片段是否合法。"""

    if "\x00" in segment:
        raise FileSpaceError("路径不能包含空字符。")
    if segment not in {".", ".."} and any(char in WINDOWS_INVALID_CHARS for char in segment):
        raise FileSpaceError(f"路径片段包含非法字符：{segment}")


def unique_child_path(parent: Path, filename: str) -> Path:
    """在目录下生成不覆盖现有文件的唯一路径。"""

    candidate = parent / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 1
    while True:
        next_candidate = parent / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def directory_size(path: Path) -> int:
    """统计目录中文件总大小。"""

    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


storage_manager = StorageManager()
