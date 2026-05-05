from __future__ import annotations

from io import BytesIO
from enum import StrEnum
from dataclasses import dataclass
from pathlib import Path

from nonebot.adapters import Bot as BaseBot
from nonebot.adapters.onebot.v11 import Bot as V11Bot
from nonebot_plugin_alconna import File, Image, Other

from src.commands import CommandExecutionContext, CommandResult, command_executor
from utils.config import global_config
from utils.models import User
from utils.session import BaseSession
from utils.storage import FileEntry, FileSpace, FileSpaceError, PathEscapeError, StorageManager, storage_manager
from utils.tools import StringCard, download_file

Attachment = File | Image | Other


class EntryIcon(StrEnum):
    """定义文件列表中不同条目类型使用的图标。"""

    directory = "📁"
    file = "📄"


@dataclass(frozen=True)
class UploadPayload:
    """表示一次可保存的消息附件。"""

    name: str
    data: bytes | None = None
    path: Path | None = None


def get_event_file_space(platform: BaseSession, user: User) -> FileSpace:
    """根据当前事件解析文件空间。

    Args:
        platform: 当前消息会话信息。
        user: 当前系统用户。

    Returns:
        FileSpace: 私聊返回个人空间，群聊返回群空间。

    Raises:
        FileSpaceError: 群聊缺少群 ID 或用户信息异常。
    """

    if platform.is_group:
        if platform.channel_id is None:
            raise FileSpaceError("当前群组缺少可用的群 ID。")
        return storage_manager.group_space(platform.channel_id)
    return storage_manager.user_space(user.id)


def get_context_file_space(context: CommandExecutionContext, manager: StorageManager | None = None) -> FileSpace:
    """根据统一命令上下文解析文件空间。

    Args:
        context: Agent 或系统调用命令时传入的执行上下文。
        manager: 文件空间管理器。

    Returns:
        FileSpace: 解析后的文件空间。

    Raises:
        FileSpaceError: 上下文缺少用户 ID 或群 ID。
    """

    manager = manager or storage_manager
    if context.channel_id:
        return manager.group_space(context.channel_id)
    if context.user_id is None:
        raise FileSpaceError("缺少用户 ID，无法定位个人文件空间。")
    return manager.user_space(context.user_id)


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
        icon = EntryIcon.directory if entry.is_dir else EntryIcon.file
        card.text(f"{icon} {entry.name}")
    if len(entries) > 50:
        card.text(f"...已截断展示，剩余 {len(entries) - 50} 项")
    return card.render()


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
        space = get_context_file_space(context)
        return _ok(space.pwd(), path=space.pwd())
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("ls")
async def execute_ls(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``ls`` 命令。"""

    try:
        space = get_context_file_space(context)
        display, entries = space.list_entries(_param(params, "path", "路径"))
        output = format_entries(f"文件列表 | {display}", entries)
        return _ok(output, path=display, entries=[entry.__dict__ for entry in entries])
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("cd")
async def execute_cd(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``cd`` 命令。"""

    try:
        space = get_context_file_space(context)
        path = space.cd(_param(params, "path", "路径"))
        return _ok(f"当前路径：{path}", path=path)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("mkdir")
async def execute_mkdir(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``mkdir`` 命令。"""

    try:
        space = get_context_file_space(context)
        path = space.mkdir(_param(params, "path", "路径", default=""))
        return _ok(f"目录创建成功：{path}", path=path)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("touch")
async def execute_touch(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``touch`` 命令。"""

    try:
        space = get_context_file_space(context)
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
        space = get_context_file_space(context)
        deleted = [result for path in paths if (result := space.remove(path, recursive=recursive, force=force))]
        return _ok("删除完成：" + ("、".join(deleted) if deleted else "没有匹配文件"), paths=deleted)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))


@command_executor.handler("cat")
async def execute_cat(params: dict, context: CommandExecutionContext) -> CommandResult:
    """执行 service 风格的 ``cat`` 命令。"""

    try:
        space = get_context_file_space(context)
        path, text, truncated = space.read_text(_param(params, "path", "路径", default=""))
        suffix = "\n...内容较长，已截断" if truncated else ""
        return _ok(f"{path}\n{text}{suffix}", path=path, truncated=truncated)
    except FileSpaceError as error:
        return CommandResult.fail(handle_space_error(error))
