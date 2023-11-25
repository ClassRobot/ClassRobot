from typing import Annotated

from nonebot.params import Depends
from nonebot.matcher import Matcher
from utils.models.depends import get_class_table
from utils.models.models import Teacher, ClassTable


async def _class_table(
    matcher: Matcher, class_name: str, teacher: Teacher
) -> ClassTable:
    if class_table := await get_class_table(
        class_name, teacher=None if class_name.isdigit() else teacher
    ):  # 输入的班级是否存在
        return class_table
    await matcher.finish(f"[{class_name}]班级不存在！")


ClassTableDepends = Annotated[ClassTable, Depends(_class_table)]
