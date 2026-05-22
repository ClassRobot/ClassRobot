from nonebot.adapters import Bot, Event
from nonebot_plugin_alconna import AlconnaMatcher

from src.shared import Emoji
from src.models.depends import UserOrCreatedDepends
from src.platform.session import EventSession

from .commands import (
    cat_cmd,
    cd_cmd,
    find_cmd,
    grep_cmd,
    ls_cmd,
    mkdir_cmd,
    pwd_cmd,
    rm_cmd,
    touch_cmd,
    tree_cmd,
    upload_file_cmd,
)
from .services import (
    collect_upload_payloads,
    find_file_entries,
    format_entries,
    format_find_results,
    format_grep_results,
    format_tree_results,
    get_event_file_space,
    grep_file_contents,
    handle_space_error,
    build_tree_lines,
    parse_rm_args,
)


@pwd_cmd.handle()
async def _(event: Event, matcher: AlconnaMatcher, platform: EventSession, user: UserOrCreatedDepends):
    """查看当前文件空间路径。"""

    try:
        space = await get_event_file_space(platform, user, event)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    await matcher.finish(space.pwd())


@ls_cmd.handle()
async def _(
    event: Event,
    matcher: AlconnaMatcher,
    platform: EventSession,
    user: UserOrCreatedDepends,
    path: str | None = None,
):
    """列出当前文件空间中的文件和目录。"""

    try:
        space = await get_event_file_space(platform, user, event)
        display, entries = space.list_entries(path)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    await matcher.finish(format_entries(f"文件列表 | {display}", entries))


@cd_cmd.handle()
async def _(
    event: Event,
    matcher: AlconnaMatcher,
    platform: EventSession,
    user: UserOrCreatedDepends,
    path: str | None = None,
):
    """切换当前文件空间目录。"""

    try:
        space = await get_event_file_space(platform, user, event)
        current_path = space.cd(path)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    await matcher.finish(Emoji.success + f"当前路径：{current_path}")


@mkdir_cmd.handle()
async def _(event: Event, matcher: AlconnaMatcher, platform: EventSession, user: UserOrCreatedDepends, path: str):
    """创建目录。"""

    try:
        space = await get_event_file_space(platform, user, event)
        created_path = space.mkdir(path)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    await matcher.finish(Emoji.success + f"目录创建成功：{created_path}")


@touch_cmd.handle()
async def _(event: Event, matcher: AlconnaMatcher, platform: EventSession, user: UserOrCreatedDepends, path: str):
    """创建空文件。"""

    try:
        space = await get_event_file_space(platform, user, event)
        created_path = space.touch(path)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    await matcher.finish(Emoji.success + f"文件创建成功：{created_path}")


@rm_cmd.handle()
async def _(
    event: Event,
    matcher: AlconnaMatcher,
    platform: EventSession,
    user: UserOrCreatedDepends,
    rm_args: tuple[str, ...],
):
    """删除文件或目录。"""

    paths, recursive, force = parse_rm_args(rm_args)
    if not paths:
        await matcher.finish(Emoji.error + "请提供要删除的路径。")

    try:
        space = await get_event_file_space(platform, user, event)
        deleted = [result for path in paths if (result := space.remove(path, recursive=recursive, force=force))]
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))

    if deleted:
        await matcher.finish(Emoji.success + "删除完成：" + "、".join(deleted))
    await matcher.finish(Emoji.warning + "没有匹配文件。")


@cat_cmd.handle()
async def _(event: Event, matcher: AlconnaMatcher, platform: EventSession, user: UserOrCreatedDepends, path: str):
    """查看文本文件内容。"""

    try:
        space = await get_event_file_space(platform, user, event)
        display, text, truncated = space.read_text(path)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    suffix = "\n...内容较长，已截断" if truncated else ""
    await matcher.finish(f"{display}\n{text}{suffix}")


@find_cmd.handle()
async def _(
    event: Event,
    matcher: AlconnaMatcher,
    platform: EventSession,
    user: UserOrCreatedDepends,
    pattern: str,
    path: str | None = None,
):
    """按名称或路径查找文件。"""

    try:
        space = await get_event_file_space(platform, user, event)
        display, entries, truncated = find_file_entries(space, pattern, path)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    await matcher.finish(format_find_results(pattern, display, entries, truncated))


@grep_cmd.handle()
async def _(
    event: Event,
    matcher: AlconnaMatcher,
    platform: EventSession,
    user: UserOrCreatedDepends,
    keyword: str,
    path: str | None = None,
):
    """搜索文本文件内容。"""

    try:
        space = await get_event_file_space(platform, user, event)
        display, matches, truncated = grep_file_contents(space, keyword, path)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    await matcher.finish(format_grep_results(keyword, display, matches, truncated))


@tree_cmd.handle()
async def _(
    event: Event,
    matcher: AlconnaMatcher,
    platform: EventSession,
    user: UserOrCreatedDepends,
    path: str | None = None,
    max_depth: int | None = None,
):
    """查看文件树。"""

    try:
        space = await get_event_file_space(platform, user, event)
        display, lines, truncated = build_tree_lines(space, path, max_depth)
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))
    await matcher.finish(format_tree_results(display, lines, truncated))


@upload_file_cmd.handle()
async def _(
    bot: Bot,
    event: Event,
    matcher: AlconnaMatcher,
    platform: EventSession,
    user: UserOrCreatedDepends,
    upload_items: tuple,
):
    """保存消息附件到当前文件空间。"""

    target_dir, payloads = await collect_upload_payloads(bot, upload_items)
    if not payloads:
        await matcher.finish(Emoji.error + "没有识别到可保存的文件附件。")

    try:
        space = await get_event_file_space(platform, user, event)
        saved_paths: list[str] = []
        for payload in payloads:
            if payload.path is not None:
                saved_paths.append(space.save_path(payload.name, payload.path, target_dir))
            elif payload.data is not None:
                saved_paths.append(space.save_bytes(payload.name, payload.data, target_dir))
    except Exception as error:
        await matcher.finish(Emoji.error + handle_space_error(error))

    await matcher.finish(Emoji.success + "文件保存成功：\n" + "\n".join(saved_paths))
