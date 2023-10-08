from utils.models import Teacher
from nonebot import on_command
from utils.auth import TEACHER
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from utils.tools import MessageArgs
from nonebot.permission import SUPERUSER
from django.db.utils import IntegrityError
from nonebot.adapters.onebot.v11 import Message
from nonebot.params import CommandArg, ArgPlainText

add_teacher = on_command("添加教师", aliases={"添加老师"}, priority=100, block=True)
del_teacher = on_command(
    "删除教师", aliases={"删除老师"}, priority=100, block=True, permission=SUPERUSER
)


# --------------------------------- 添加教师 ---------------------------------
@add_teacher.handle()
async def _(
    state: T_State, matcher: Matcher, msg: Message = CommandArg(), _: Teacher = TEACHER
):
    state["args"] = MessageArgs({"qq": "QQ", "name": "姓名", "phone": "电话"}, matcher)
    if text := msg.get("text"):
        state["params"] = text


@add_teacher.got("params", prompt="请依次告诉我QQ、姓名、电话")
async def _(state: T_State, matcher: Matcher, params: str = ArgPlainText()):
    try:
        args = await state["args"](params)
        await Teacher.objects.acreate(**args, creator=state["teacher"].qq)
        await matcher.finish("OK")
    except IntegrityError:
        await matcher.finish("好像已经存在了呢")


# --------------------------------- 删除教师 ---------------------------------
@del_teacher.handle()
async def _(matcher: Matcher, msg: Message = CommandArg()):
    if text := msg.extract_plain_text():
        await Teacher.objects.filter(qq__in=[qq for qq in text.split()]).adelete()
        await matcher.finish("OK")


__helper__ = [
    {
        "cmd": "添加教师",
        "alias": ["添加老师"],
        "params": ["QQ", "姓名", "电话"],
        "tags": ["添加", "教师"],
        "doc": "添加教师后开始后续功能，教师也可以添加别的用户为教师。\nPS:教师拥有添加教师的能力但不要随意添加，每一位添加上去的教师都会有被谁添加的记录！！！",
    },
    {
        "cmd": "删除教师",
        "alias": ["删除老师"],
        "params": ["QQ"],
        "tags": ["删除", "教师"],
        "doc": "删除教师只有机器人管理员才能删除，其他无论是学生和教师都无法删除！",
    },
]
