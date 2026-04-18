from utils import Emoji
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher

from .commands import campus_map_cmd
from .depends import CampusMapDepends


@campus_map_cmd.handle()
async def _(matcher: AlconnaMatcher, campus_map: CampusMapDepends, position: list[str]):
    """处理当前命令或事件逻辑。"""
    location = await campus_map.parse_location(" ".join(position))
    if not location:
        await matcher.finish(Emoji.error + "没有找到该地点")

    await matcher.send(UniMessage.image(raw=await campus_map.to_pic(location)))
