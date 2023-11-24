from nonebot.matcher import Matcher
from utils.models.models import Teacher
from utils.models.depends import create_student

from .commands import add_student_cmd


@add_student_cmd.handle()
async def _(
    matcher: Matcher, teacher: Teacher, name: str, class_name: str, user_id: int
):
    ...
