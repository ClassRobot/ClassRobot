from src.shared import Emoji
from nonebot.adapters import Bot, Event
from src.platform.session import EventSession
from nonebot_plugin_alconna import AlconnaMatcher
from src.platform.session.depends import UserOrCreatedDepends

from .commands import rm_cmd, mkdir_cmd, touch_cmd, upload_file_cmd
from .services import parse_rm_args, handle_space_error, get_event_file_space, collect_upload_payloads


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
