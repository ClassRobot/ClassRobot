from __future__ import annotations

from io import BytesIO
from enum import StrEnum
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from nonebot.adapters import Bot as BaseBot, Event
from nonebot.adapters.onebot.v11 import Bot as V11Bot
from nonebot_plugin_alconna import File, Image, Other
from pydantic import BaseModel

from utils.commands import CommandExecutionContext, CommandResult, command_executor
from utils.config import global_config
from utils.models import User
from utils.session import BaseSession
from core.storage import FileEntry, FileSpace, FileSpaceError, PathEscapeError, StorageManager, storage_manager
from utils.tools import StringCard, download_file

from .virtual import (
    VirtualFileWorkspace,
    display_path_from_parts,
    build_context_file_workspace,
    build_event_file_workspace,
    resolve_platform_group_id,
)

Attachment = File | Image | Other
DEFAULT_TREE_DEPTH = 3
MAX_TREE_DEPTH = 8
MAX_TREE_ENTRIES = 200
MAX_FIND_SCAN = 2000
MAX_FIND_RESULTS = 50
MAX_GREP_SCAN = 1000
MAX_GREP_RESULTS = 50
MAX_GREP_FILE_SIZE = 256 * 1024
GREP_TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".log",
    ".md",
    ".py",
    ".text",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


class EntryIcon(StrEnum):
    """定义文件列表中不同条目类型使用的图标。"""

    mount = "🔗"
    directory = "📁"
    file = "📄"


@dataclass(frozen=True)
class UploadPayload:
    """表示一次可保存的消息附件。"""

    name: str
    data: bytes | None = None
    path: Path | None = None


class GrepMatch(BaseModel):
    """表示一次文本搜索命中。"""

    path: str
    line_no: int
    text: str


async def resolve_platform_group_space_id(platform: BaseSession, event: Event | None = None) -> int:
    """把平台群聊上下文解析为系统群组主键。

    Args:
        platform: 当前消息会话信息。
        event: 可选的原始事件；当群组尚未绑定时用于自动创建系统群组。

    Returns:
        int: 系统内 ``Group.id``。
    """

    return await resolve_platform_group_id(platform, event)


async def get_event_file_space(
    platform: BaseSession,
    user: User,
    event: Event | None = None,
) -> VirtualFileWorkspace:
    """根据当前事件解析文件管理虚拟工作区。

    Args:
        platform: 当前消息会话信息。
        user: 当前系统用户。
        event: 可选的原始事件；群聊首次入库时用于自动创建系统群组挂载。

    Returns:
        VirtualFileWorkspace: 以个人空间为根、外部空间为挂载的工作区。
    """

    return await build_event_file_workspace(platform, user, event, manager=storage_manager)


async def get_context_file_space(
    context: CommandExecutionContext,
    manager: StorageManager | None = None,
) -> VirtualFileWorkspace:
    """根据统一命令上下文解析文件管理虚拟工作区。

    Args:
        context: Agent 或系统调用命令时传入的执行上下文。
        manager: 文件空间管理器。

    Returns:
        VirtualFileWorkspace: 解析后的虚拟工作区。
    """

    return await build_context_file_workspace(context, manager=manager or storage_manager)


def format_entries(title: str, entries: list[FileEntry]) -> str:
    """把文件列表渲染为文本卡片。

    Args:
        title: 卡片标题。
        entries: 文件条目列表。

    Returns:
        str: 渲染后的文本。
    """

    card = StringCard(title)
    if not entries:
        card.text("目录为空")
        return card.render()

    for entry in entries[:50]:
        icon = EntryIcon.mount if entry.is_mount else EntryIcon.directory if entry.is_dir else EntryIcon.file
        suffix = ""
        if entry.is_mount:
            access = "只读" if entry.readonly else "可写"
            title = f" - {entry.title}" if entry.title else ""
            suffix = f"{title} [{access}]"
        card.text(f"{icon} {entry.name}{suffix}")
    if len(entries) > 50:
        card.text(f"...已截断展示，剩余 {len(entries) - 50} 项")
    return card.render()


def find_file_entries(
    space: FileSpace | VirtualFileWorkspace,
    pattern: str,
    path: str | None = None,
    *,
    max_results: int = MAX_FIND_RESULTS,
    max_scan: int = MAX_FIND_SCAN,
) -> tuple[str, list[FileEntry], bool]:
    """在当前文件空间内按名称或展示路径查找文件。

    Args:
        space: 当前文件空间。
        pattern: 文件名或路径关键词。
        path: 可选搜索起点，默认使用当前工作目录。
        max_results: 最多返回条目数。
        max_scan: 最多扫描条目数。

    Returns:
        tuple[str, list[FileEntry], bool]: 搜索起点、命中条目、是否因上限被截断。

    Raises:
        FileSpaceError: 搜索起点不存在。
        PathEscapeError: 搜索路径尝试越界。
    """

    if isinstance(space, VirtualFileWorkspace):
        return find_workspace_file_entries(space, pattern, path, max_results=max_results, max_scan=max_scan)

    keyword = normalize_search_keyword(pattern)
    resolved = space.resolve(path, reject_escape=True)
    if not resolved.path.exists():
        raise FileSpaceError(f"路径不存在：{resolved.display}")

    candidates, scan_truncated = collect_search_candidates(resolved.path, max_scan=max_scan)
    results: list[FileEntry] = []
    for candidate in candidates:
        entry = file_entry_from_path(space, candidate)
        haystack = f"{entry.name} {entry.path}".lower()
        if keyword not in haystack:
            continue
        results.append(entry)
        if len(results) >= max_results:
            return resolved.display, results, True
    return resolved.display, results, scan_truncated


def grep_file_contents(
    space: FileSpace | VirtualFileWorkspace,
    keyword: str,
    path: str | None = None,
    *,
    max_results: int = MAX_GREP_RESULTS,
    max_scan: int = MAX_GREP_SCAN,
) -> tuple[str, list[GrepMatch], bool]:
    """在当前文件空间内搜索文本文件内容。

    Args:
        space: 当前文件空间。
        keyword: 文本关键词。
        path: 可选搜索起点，默认使用当前工作目录。
        max_results: 最多返回命中行数。
        max_scan: 最多扫描文件或目录条目数。

    Returns:
        tuple[str, list[GrepMatch], bool]: 搜索起点、命中行、是否因上限被截断。

    Raises:
        FileSpaceError: 搜索起点不存在。
        PathEscapeError: 搜索路径尝试越界。
    """

    if isinstance(space, VirtualFileWorkspace):
        return grep_workspace_file_contents(space, keyword, path, max_results=max_results, max_scan=max_scan)

    needle = normalize_search_keyword(keyword)
    resolved = space.resolve(path, reject_escape=True)
    if not resolved.path.exists():
        raise FileSpaceError(f"路径不存在：{resolved.display}")

    candidates, scan_truncated = collect_search_candidates(resolved.path, max_scan=max_scan)
    results: list[GrepMatch] = []
    for candidate in candidates:
        if not is_searchable_text_file(candidate):
            continue
        for match in iter_file_text_matches(space, candidate, needle):
            results.append(match)
            if len(results) >= max_results:
                return resolved.display, results, True
    return resolved.display, results, scan_truncated


def build_tree_lines(
    space: FileSpace | VirtualFileWorkspace,
    path: str | None = None,
    max_depth: int | None = None,
    *,
    max_entries: int = MAX_TREE_ENTRIES,
) -> tuple[str, list[str], bool]:
    """构建当前文件空间内的目录树文本。

    Args:
        space: 当前文件空间。
        path: 可选树根路径，默认使用当前工作目录。
        max_depth: 最大展示深度，默认 ``DEFAULT_TREE_DEPTH``。
        max_entries: 最多展示条目数。

    Returns:
        tuple[str, list[str], bool]: 树根路径、树文本行、是否因上限被截断。

    Raises:
        FileSpaceError: 树根路径不存在。
        PathEscapeError: 树根路径尝试越界。
    """

    if isinstance(space, VirtualFileWorkspace):
        return build_workspace_tree_lines(space, path, max_depth, max_entries=max_entries)

    normalized_path, depth_limit = normalize_tree_args(path, max_depth)
    resolved = space.resolve(normalized_path, reject_escape=True)
    if not resolved.path.exists():
        raise FileSpaceError(f"路径不存在：{resolved.display}")
    if resolved.path.is_file():
        return resolved.display, [f"{EntryIcon.file} {resolved.display}"], False

    lines = [f"{EntryIcon.directory} {resolved.display}"]
    rendered = 0
    truncated = False

    def append_children(directory: Path, prefix: str, depth: int) -> None:
        nonlocal rendered, truncated
        if depth > depth_limit or truncated:
            return

        children = visible_children(directory)
        for index, child in enumerate(children):
            if rendered >= max_entries:
                truncated = True
                return

            is_last = index == len(children) - 1
            connector = "└──" if is_last else "├──"
            icon = EntryIcon.directory if child.is_dir() else EntryIcon.file
            suffix = "/" if child.is_dir() else ""
            lines.append(f"{prefix}{connector} {icon} {child.name}{suffix}")
            rendered += 1

            if child.is_dir() and depth < depth_limit:
                next_prefix = prefix + ("    " if is_last else "│   ")
                append_children(child, next_prefix, depth + 1)

    append_children(resolved.path, "", 1)
    return resolved.display, lines, truncated


def find_workspace_file_entries(
    workspace: VirtualFileWorkspace,
    pattern: str,
    path: str | None = None,
    *,
    max_results: int,
    max_scan: int,
) -> tuple[str, list[FileEntry], bool]:
    """在虚拟工作区覆盖范围内按名称或路径查找文件。

    Args:
        workspace: 当前虚拟文件工作区。
        pattern: 文件名或路径关键词。
        path: 可选搜索起点。
        max_results: 最多返回条目数。
        max_scan: 最多扫描条目数。

    Returns:
        tuple[str, list[FileEntry], bool]: 搜索起点、命中条目、是否截断。
    """

    keyword = normalize_search_keyword(pattern)
    display, targets = workspace.search_targets(path)
    results: list[FileEntry] = []
    scanned = 0
    truncated = False

    for target in targets:
        if target.path is None or target.space is None:
            continue
        if scanned >= max_scan:
            truncated = True
            break
        candidates, scan_truncated = collect_search_candidates(target.path, max_scan=max_scan - scanned)
        scanned += len(candidates)
        truncated = truncated or scan_truncated
        for candidate in candidates:
            entry = file_entry_from_path(
                target.space, candidate, virtual_prefix=target.full_parts[:2] if target.mount else ()
            )
            haystack = f"{entry.name} {entry.path}".lower()
            if keyword not in haystack:
                continue
            results.append(entry)
            if len(results) >= max_results:
                return display, results, True
    return display, results, truncated


def grep_workspace_file_contents(
    workspace: VirtualFileWorkspace,
    keyword: str,
    path: str | None = None,
    *,
    max_results: int,
    max_scan: int,
) -> tuple[str, list[GrepMatch], bool]:
    """在虚拟工作区覆盖范围内搜索文本文件内容。

    Args:
        workspace: 当前虚拟文件工作区。
        keyword: 文本关键词。
        path: 可选搜索起点。
        max_results: 最多返回命中行数。
        max_scan: 最多扫描文件或目录条目数。

    Returns:
        tuple[str, list[GrepMatch], bool]: 搜索起点、命中行、是否截断。
    """

    needle = normalize_search_keyword(keyword)
    display, targets = workspace.search_targets(path)
    results: list[GrepMatch] = []
    scanned = 0
    truncated = False

    for target in targets:
        if target.path is None or target.space is None:
            continue
        if scanned >= max_scan:
            truncated = True
            break
        candidates, scan_truncated = collect_search_candidates(target.path, max_scan=max_scan - scanned)
        scanned += len(candidates)
        truncated = truncated or scan_truncated
        for candidate in candidates:
            if not is_searchable_text_file(candidate):
                continue
            for match in iter_file_text_matches(
                target.space,
                candidate,
                needle,
                virtual_prefix=target.full_parts[:2] if target.mount else (),
            ):
                results.append(match)
                if len(results) >= max_results:
                    return display, results, True
    return display, results, truncated


def build_workspace_tree_lines(
    workspace: VirtualFileWorkspace,
    path: str | None = None,
    max_depth: int | None = None,
    *,
    max_entries: int,
) -> tuple[str, list[str], bool]:
    """构建虚拟工作区目录树。

    Args:
        workspace: 当前虚拟文件工作区。
        path: 可选树根路径。
        max_depth: 最大展示深度。
        max_entries: 最多展示条目数。

    Returns:
        tuple[str, list[str], bool]: 树根路径、树文本行、是否截断。
    """

    normalized_path, depth_limit = normalize_tree_args(path, max_depth)
    display, entries = workspace.list_entries(normalized_path)
    if len(entries) == 1 and entries[0].path == display and not entries[0].is_dir:
        return display, [f"{EntryIcon.file} {display}"], False

    lines = [f"{EntryIcon.directory} {display}"]
    rendered = 0
    truncated = False

    def append_children(children: Iterable[FileEntry], prefix: str, depth: int) -> None:
        nonlocal rendered, truncated
        if depth > depth_limit or truncated:
            return

        visible = list(children)
        for index, child in enumerate(visible):
            if rendered >= max_entries:
                truncated = True
                return

            is_last = index == len(visible) - 1
            connector = "└──" if is_last else "├──"
            icon = EntryIcon.mount if child.is_mount else EntryIcon.directory if child.is_dir else EntryIcon.file
            suffix = "" if child.name.endswith("/") or not child.is_dir else "/"
            title = f" - {child.title}" if child.is_mount and child.title else ""
            lines.append(f"{prefix}{connector} {icon} {child.name}{suffix}{title}")
            rendered += 1

            if child.is_dir and depth < depth_limit:
                try:
                    _, nested = workspace.list_entries(child.path)
                except FileSpaceError:
                    continue
                next_prefix = prefix + ("    " if is_last else "│   ")
                append_children(nested, next_prefix, depth + 1)

    append_children(entries, "", 1)
    return display, lines, truncated


def format_find_results(pattern: str, display: str, entries: list[FileEntry], truncated: bool) -> str:
    """渲染 ``find`` 命令结果。"""

    card = StringCard(f"查找文件 | {display}")
    card.text(f"关键词：{pattern}")
    if not entries:
        card.text("没有找到匹配文件")
        return card.render()
    for entry in entries:
        icon = EntryIcon.directory if entry.is_dir else EntryIcon.file
        card.text(f"{icon} {entry.path}")
    if truncated:
        card.text("结果较多，已按上限截断")
    return card.render()


def format_grep_results(keyword: str, display: str, matches: list[GrepMatch], truncated: bool) -> str:
    """渲染 ``grep`` 命令结果。"""

    card = StringCard(f"内容搜索 | {display}")
    card.text(f"关键词：{keyword}")
    if not matches:
        card.text("没有找到匹配内容")
        return card.render()
    for match in matches:
        card.text(f"{match.path}:{match.line_no}: {match.text}")
    if truncated:
        card.text("结果较多，已按上限截断")
    return card.render()


def format_tree_results(display: str, lines: list[str], truncated: bool) -> str:
    """渲染 ``tree`` 命令结果。"""

    card = StringCard(f"文件树 | {display}")
    for line in lines:
        card.text(line)
    if truncated:
        card.text("目录较大，已按上限截断")
    return card.render()


def normalize_search_keyword(value: str) -> str:
    """清理搜索关键词。"""

    keyword = str(value or "").strip().lower()
    if not keyword:
        raise FileSpaceError("搜索关键词不能为空。")
    return keyword


def normalize_tree_args(path: str | None, max_depth: int | None) -> tuple[str | None, int]:
    """归一化 ``tree`` 的路径和深度参数。"""

    if max_depth is None and isinstance(path, str) and path.strip().isdigit():
        max_depth = int(path.strip())
        path = None
    depth = DEFAULT_TREE_DEPTH if max_depth is None else int(max_depth)
    return path, max(0, min(depth, MAX_TREE_DEPTH))


def collect_search_candidates(root: Path, *, max_scan: int) -> tuple[list[Path], bool]:
    """收集可搜索路径，跳过隐藏项和符号链接。"""

    if root.is_symlink():
        return [], False
    if root.is_file():
        return [root], False

    candidates: list[Path] = []
    truncated = False

    def walk(directory: Path) -> None:
        nonlocal truncated
        for child in visible_children(directory):
            if len(candidates) >= max_scan:
                truncated = True
                return
            candidates.append(child)
            if child.is_dir():
                walk(child)
                if truncated:
                    return

    walk(root)
    return candidates, truncated


def visible_children(directory: Path) -> list[Path]:
    """列出目录下可展示的子项。"""

    try:
        children = [child for child in directory.iterdir() if not child.name.startswith(".") and not child.is_symlink()]
    except OSError:
        return []
    children.sort(key=lambda item: (not item.is_dir(), item.name.lower()))
    return children


def file_entry_from_path(
    space: FileSpace,
    path: Path,
    *,
    virtual_prefix: tuple[str, ...] = (),
) -> FileEntry:
    """把真实路径转换成搜索结果条目。"""

    relative_parts = tuple(path.resolve(strict=False).relative_to(space.home_dir.resolve()).parts)
    is_dir = path.is_dir()
    display_parts = (*virtual_prefix, *relative_parts)
    return FileEntry(
        name=path.name + ("/" if is_dir else ""),
        path=display_path_from_parts(display_parts) if virtual_prefix else space.display_path(relative_parts),
        is_dir=is_dir,
        size=None,
    )


def is_searchable_text_file(path: Path) -> bool:
    """判断文件是否适合进行文本搜索。"""

    if not path.is_file() or path.is_symlink():
        return False
    try:
        if path.stat().st_size > MAX_GREP_FILE_SIZE:
            return False
    except OSError:
        return False
    return path.suffix.lower() in GREP_TEXT_SUFFIXES or not path.suffix


def iter_file_text_matches(
    space: FileSpace,
    path: Path,
    keyword: str,
    *,
    virtual_prefix: tuple[str, ...] = (),
):
    """逐行生成单个文本文件中的搜索命中。"""

    try:
        with path.open("r", encoding="utf-8", errors="ignore") as file:
            for line_no, line in enumerate(file, start=1):
                text = " ".join(line.strip().split())
                if keyword in text.lower():
                    yield GrepMatch(
                        path=file_entry_from_path(space, path, virtual_prefix=virtual_prefix).path,
                        line_no=line_no,
                        text=truncate_text(text, 160),
                    )
    except OSError:
        return


def truncate_text(value: str, limit: int) -> str:
    """把过长文本压缩到适合聊天展示的长度。"""

    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def parse_rm_args(values: tuple[str, ...] | list[str]) -> tuple[list[str], bool, bool]:
    """解析 ``rm`` 命令参数。

    Args:
        values: 用户输入的删除参数。

    Returns:
        tuple[list[str], bool, bool]: 路径列表、是否递归、是否强制。
    """

    paths: list[str] = []
    recursive = False
    force = False
    for value in values:
        value = value.strip()
        if not value:
            continue
        if value in {"-r", "-R", "--recursive"}:
            recursive = True
            continue
        if value in {"-f", "--force"}:
            force = True
            continue
        if value in {"-rf", "-fr", "-Rf", "-fR"}:
            recursive = True
            force = True
            continue
        paths.append(value)
    return paths, recursive, force


async def collect_upload_payloads(bot: BaseBot, items: tuple) -> tuple[str | None, list[UploadPayload]]:
    """从 Alconna 参数中提取目标目录和附件数据。

    Args:
        bot: 当前 Bot 对象。
        items: ``上传文件`` 命令解析出的参数。

    Returns:
        tuple[str | None, list[UploadPayload]]: 目标目录和附件列表。
    """

    target_dir: str | None = None
    payloads: list[UploadPayload] = []

    for item in items:
        if isinstance(item, str):
            text = item.strip()
            if text and target_dir is None:
                target_dir = text
            continue
        if isinstance(item, File | Image):
            data = payload_data_from_segment(item)
            if data is None and item.url:
                data = await download_file(item.url)
            if data is None:
                continue
            payloads.append(
                UploadPayload(
                    name=getattr(item, "name", None) or ("image" if isinstance(item, Image) else "file"),
                    data=data,
                )
            )
            continue
        if isinstance(item, Other):
            payload = await payload_from_other(bot, item)
            if payload is not None:
                payloads.append(payload)
    return target_dir, payloads


def payload_data_from_segment(item: File | Image) -> bytes | None:
    """从通用文件段中读取内联数据或本地路径数据。

    Args:
        item: Alconna 解析出的文件或图片段。

    Returns:
        bytes | None: 能读取到数据时返回字节，否则返回 ``None``。
    """

    raw = getattr(item, "raw", None)
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, BytesIO):
        return raw.getvalue()

    path = getattr(item, "path", None)
    if path:
        file_path = Path(path)
        if file_path.exists() and file_path.is_file():
            return file_path.read_bytes()
    return None


async def payload_from_other(bot: BaseBot, item: Other) -> UploadPayload | None:
    """从 OneBot V11 原始文件消息中读取附件。"""

    origin = item.origin
    if origin.type != "file" or not isinstance(bot, V11Bot):
        return None

    file_id = str(origin.data.get("file_id") or "")
    if not file_id:
        return None
    response = await bot.get_file(file_id=file_id)
    source = Path(response["file"])
    if global_config.wsl_share_dir and global_config.wsl_share_dir.exists():
        source = global_config.wsl_share_dir / source.name
    return UploadPayload(
        name=str(origin.data.get("file_name") or source.name or file_id),
        path=source,
    )


def handle_space_error(error: Exception) -> str:
    """把文件空间异常转换为用户提示。"""

    if isinstance(error, PathEscapeError):
        return "路径越界：不能访问当前文件空间之外的目录。"
    if isinstance(error, FileSpaceError):
        return str(error)
    raise error


def _param(params: dict, *names: str, default=None):
    """按多个可能名称读取 service 参数。"""

    for name in names:
        if name in params:
            return params[name]
    return default


def _ok(message: str, **data) -> CommandResult:
    """构造带结构化数据的命令结果。"""

    return CommandResult.ok(message, data=data)


@command_executor.handler("pwd")
async def execute_pwd(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``pwd`` 命令。"""

    try:
        space = await get_context_file_space(context)
        return _ok(space.pwd(), path=space.pwd())
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("ls")
async def execute_ls(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``ls`` 命令。"""

    try:
        space = await get_context_file_space(context)
        display, entries = space.list_entries(_param(params, "path", "路径"))
        output = format_entries(f"文件列表 | {display}", entries)
        return _ok(output, path=display, entries=[entry.__dict__ for entry in entries])
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("cd")
async def execute_cd(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``cd`` 命令。"""

    try:
        space = await get_context_file_space(context)
        path = space.cd(_param(params, "path", "路径"))
        return _ok(f"当前路径：{path}", path=path)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("mkdir")
async def execute_mkdir(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``mkdir`` 命令。"""

    try:
        space = await get_context_file_space(context)
        path = space.mkdir(_param(params, "path", "路径", default=""))
        return _ok(f"目录创建成功：{path}", path=path)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("touch")
async def execute_touch(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``touch`` 命令。"""

    try:
        space = await get_context_file_space(context)
        path = space.touch(_param(params, "path", "路径", default=""))
        return _ok(f"文件创建成功：{path}", path=path)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("rm")
async def execute_rm(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``rm`` 命令。"""

    try:
        values = _param(params, "rm_args", "参数", default=[])
        if isinstance(values, str):
            values = [values]
        paths, recursive, force = parse_rm_args(values)
        if not paths:
            return CommandResult.fail("请提供要删除的路径。")
        space = await get_context_file_space(context)
        deleted = [result for path in paths if (result := space.remove(path, recursive=recursive, force=force))]
        return _ok("删除完成：" + ("、".join(deleted) if deleted else "没有匹配文件"), paths=deleted)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("cat")
async def execute_cat(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``cat`` 命令。"""

    try:
        space = await get_context_file_space(context)
        path, text, truncated = space.read_text(_param(params, "path", "路径", default=""))
        suffix = "\n...内容较长，已截断" if truncated else ""
        return _ok(f"{path}\n{text}{suffix}", path=path, truncated=truncated)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("find")
async def execute_find(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``find`` 命令。"""

    try:
        pattern = _param(params, "pattern", "关键词", default="")
        path = _param(params, "path", "路径")
        space = await get_context_file_space(context)
        display, entries, truncated = find_file_entries(space, pattern, path)
        output = format_find_results(str(pattern), display, entries, truncated)
        return _ok(
            output,
            path=display,
            pattern=str(pattern),
            truncated=truncated,
            entries=[entry.__dict__ for entry in entries],
        )
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("grep")
async def execute_grep(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``grep`` 命令。"""

    try:
        keyword = _param(params, "keyword", "关键词", default="")
        path = _param(params, "path", "路径")
        space = await get_context_file_space(context)
        display, matches, truncated = grep_file_contents(space, keyword, path)
        output = format_grep_results(str(keyword), display, matches, truncated)
        return _ok(
            output,
            path=display,
            keyword=str(keyword),
            truncated=truncated,
            matches=[match.dict() for match in matches],
        )
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("tree")
async def execute_tree(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``tree`` 命令。"""

    try:
        path = _param(params, "path", "路径")
        max_depth = _param(params, "max_depth", "深度")
        space = await get_context_file_space(context)
        display, lines, truncated = build_tree_lines(space, path, max_depth)
        output = format_tree_results(display, lines, truncated)
        return _ok(output, path=display, lines=lines, truncated=truncated)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))
