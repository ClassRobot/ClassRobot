from nonebot.params import Depends
from nonebot.adapters import Event as BaseEvent


def get_user_id(event: BaseEvent) -> str:
    return event.get_user_id()


UserId: str = Depends(get_user_id)
