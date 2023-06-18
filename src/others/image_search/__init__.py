from nonebot import on_command
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.params import ArgParam, CommandArg
from nonebot.adapters.onebot.v11.helpers import ImageURLs, extract_image_urls
from nonebot.adapters.onebot.v11 import (
    Bot,
    Message,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
    PrivateMessageEvent,
)

from .search import ImageSearch, get_url

image_search_cmd = on_command("搜图", aliases={"识番", "识别番剧"}, priority=100, block=True)


@image_search_cmd.handle()
async def _(matcher: Matcher, msg: Message = CommandArg()):
    if msg:
        matcher.set_arg("params", msg)


@image_search_cmd.got("params", prompt="给我看看是什么图片！")
async def _(bot: Bot, matcher: Matcher, event: MessageEvent):
    await matcher.send("让我看看")
    if url := get_url(matcher.get_arg("params")):  # type: ignore
        image_search = ImageSearch(url, event.self_id)
        try:
            if forward := await image_search.trace():
                if isinstance(event, GroupMessageEvent):  # 群合并转发
                    await bot.call_api(
                        "send_group_forward_msg",
                        group_id=event.group_id,
                        messages=forward,
                    )
                elif isinstance(event, PrivateMessageEvent):  # 私聊合并转发
                    await bot.call_api(
                        "send_private_forward_msg",
                        user_id=event.user_id,
                        messages=forward,
                    )
        except KeyError:
            await matcher.finish("刚才走神了，再发一次")


__helper__ = {
    "cmd": "识番",
    "alias": ["识别番剧"],
    "doc": "发送番剧的某个画面的截图来进行识别番剧",
    "use": "识别番剧 [图片]",
    "tags": ["识别", "图片"],
    "params": ["图片"],
}
