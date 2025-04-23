from utils import Emoji
from utils.models import School, College
from nonebot_plugin_alconna import AlconnaMatcher

from .commands import add_school, add_college


@add_school.handle()
async def _(matcher: AlconnaMatcher, school_name: str, address: str | None = None):
    """添加学校"""
    if await School.filter(name=school_name).exists():
        await matcher.finish(Emoji.error + "学校已存在！")
    await School(name=school_name, address=address).create()
    await matcher.finish(Emoji.success + f"学校**{school_name}**添加成功！")


@add_college.handle()
async def _(matcher: AlconnaMatcher, school_name: str, college_name: str):
    """添加学院"""
    if (school := await School.filter(name=school_name).first()) is None:
        await matcher.finish(Emoji.error + f"**{school_name}**学校不存在！")
    elif await College.filter(name=college_name, school_id=school.id).exists():
        await matcher.finish(Emoji.error + f"**{college_name}**学院已存在！")
    await College(name=college_name, school_id=school.id).create()
    await matcher.finish(Emoji.success + f"**{college_name}**添加成功！")
