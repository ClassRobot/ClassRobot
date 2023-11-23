from nonebot.params import Depends
from nonebot.matcher import Matcher
from nonebot.adapters import Event as BaseEvent
from nonebot_plugin_alconna.uniseg import MsgTarget


def get_user_id(event: BaseEvent) -> str:
    return event.get_user_id()


async def get_group_id(matcher: Matcher, target: MsgTarget) -> str:
    if target.private or target.channel:
        await matcher.finish()
    return str(target.id)


UserId: str = Depends(get_user_id)
GroupId: str = Depends(get_group_id)
