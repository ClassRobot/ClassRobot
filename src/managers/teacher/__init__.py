from utils.models import User
from nonebot_plugin_alconna import At
from utils.session import SessionPlatform

from .commands import add_teacher_cmd


@add_teacher_cmd.handle()
async def _(
    platform: SessionPlatform,
    name: str,
    phone: int,
    user_id: At | str,
    user: User,
):
    print("hello")
    print(user)
