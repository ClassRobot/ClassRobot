from nonebot import on_command
from utils.auth import TEACHER
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from utils.orm import College, Teacher
from django.db.utils import IntegrityError
from nonebot.params import CommandArg, ArgPlainText

add_college = on_command("添加学院", aliases={"添加院系"}, priority=100, block=True)
del_college = on_command("删除院系", aliases={"删除学院"}, priority=100, block=True)


# --------------------------------- 添加院系 ---------------------------------
@add_college.handle()
async def _(state: T_State, msg: Message = CommandArg(), _: Teacher = TEACHER):
    if text := msg.get("text"):
        state["params"] = text


@add_college.got("params", prompt="想叫什么呢？")
async def _(state: T_State, matcher: Matcher, params: str = ArgPlainText()):
    try:
        if params:
            await College.objects.acreate(college=params, creator=state["teacher"].qq)
            await matcher.finish("OK")
        await matcher.finish("不说算了！")
    except IntegrityError:
        await matcher.finish("已经存在了哦！")


# --------------------------------- 删除院系 ---------------------------------
@del_college.handle()
async def _(
    matcher: Matcher, state: T_State, msg: Message = CommandArg(), _: Teacher = TEACHER
):
    if text := msg.get("text"):
        state["params"] = text
    else:
        state["college"] = College.objects.all()
        await matcher.send(
            "需要删哪个？\n" + ("\n".join(i.college for i in state["college"]))
        )


@del_college.got("params")
async def _(state: T_State, matcher: Matcher, params: str = ArgPlainText()):
    try:
        await state.get("college", College.objects).filter(college=params).adelete()
        await matcher.finish("OK")
    except IntegrityError:
        await matcher.finish(f"删不掉哦，以为还有相关专业啦！")


__helper__ = [
    {
        "cmd": "添加院系",
        "doc": "只有教师才能添加院系",
        "params": ["院系名称"],
        "use": [["添加院系 信息工程", "OK"]],
        "tags": ["院系", "教师", "添加"],
    },
    {
        "cmd": "删除院系",
        "doc": "只有教师才能删除院系，并且如果要进行删除，改院系下需要没有添加过专业",
        "params": ["院系名称"],
        "use": [["删除院系 信息工程", "OK"]],
        "tags": ["院系", "教师", "删除"],
    },
]
