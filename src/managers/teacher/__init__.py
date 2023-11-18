from typing import Any, TypeAlias

from tarina import lang
from nonebot.adapters import Event
from utils.config import comp_config
from utils.session import SessionPlatform
from utils.models import User, Teacher, UserModel
from utils.auth import UserExtension, TeacherExtension
from nonebot_plugin_alconna.model import Match, CompConfig
from nonebot_plugin_alconna import At, UniMessage, AlconnaMatcher, on_alconna
from utils.models.depends import get_teacher, create_teacher, get_or_create_user

from .alconna import add_teacher_alc

lang.set("completion", "node", "")
lang.set("completion", "prompt_select", "")


add_teacher = on_alconna(
    add_teacher_alc, block=True, comp_config=comp_config, extensions=[TeacherExtension]
)


@add_teacher.handle()
async def _(
    platform: SessionPlatform,
    name: str,
    phone: int,
    user_id: At | str,
    user: User,
):
    print("hello")
    print(user)
