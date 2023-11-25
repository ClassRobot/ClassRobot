from nonebot.params import Depends
from nonebot.matcher import Matcher
from nonebot_plugin_alconna import Target
from nonebot.adapters import Event as BaseEvent
from nonebot_plugin_alconna.uniseg import MsgTarget


def get_user_id(event: BaseEvent) -> str:
    return event.get_user_id()


def get_group_id(target: Target) -> str | None:
    if not target.private:
        return str(target.id) + (f"&{target.parent_id}" if target.parent_id else "")


async def _get_group_id(matcher: Matcher, target: MsgTarget) -> str:
    if group_id := get_group_id(target):
        return group_id
    await matcher.finish()


UserId: str = Depends(get_user_id)
GroupId: str = Depends(_get_group_id)
