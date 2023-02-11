from nonebot import on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.params import CommandArg, ArgPlainText
from nonebot.matcher import Matcher
from django.db.utils import IntegrityError

from utils.orm import Teacher, Major, College
from utils.tools import MessageArgs
from utils.manages import TEACHER


add_major = on_command("添加专业", priority=100, block=True)
del_major = on_command("删除专业", priority=100, block=True)


# --------------------------------- 添加专业 ---------------------------------
@add_major.handle()
async def _(state: T_State, matcher: Matcher, msg: Message = CommandArg(), _: Teacher = TEACHER):
    state["args"] = MessageArgs({"major": "专业", "college": "院系"}, matcher,  "添加到哪个{}？")
    if text := msg.get('text'):
        state["params"] = text


@add_major.got("params", prompt="需要添加什么专业同时是哪个院系？")
async def _(state: T_State, event: MessageEvent, matcher: Matcher, params: str = ArgPlainText()):
    values: dict = await state["args"](params.split())
    if college := await College.objects.filter(college=values["college"]).afirst():
        try:
            await Major.objects.acreate(college_id=college.college_id, major=values["major"], invitee=event.user_id)
            await matcher.finish("OK")
        except IntegrityError:
            await matcher.finish(f"好像已经存在了！")
    await matcher.finish(f'{values["college"]}不存在哦！')


# --------------------------------- 删除专业 ---------------------------------
@del_major.handle()
async def _(state: T_State, msg: Message = CommandArg(), _: Teacher = TEACHER):
    if text := msg.get('text'):
        state["params"] = text


@add_major.got("params", prompt="要删哪个？")
async def _(matcher: Matcher, params: str = ArgPlainText()):
    try:
        if params:
            Major.objects.filter(major=params).delete()
            await matcher.finish("OK")
        await matcher.finish("不说算了")
    except IntegrityError:
        await matcher.finish("好像还有对应班级在，你不能删掉！")


__helper__ = [{
    "cmd": "添加专业",
    "params": ["专业名称", "院系名称"],
    "tags": ["专业", "添加", "教师"],
    "use": [["添加专业 人工智能", "添加到哪个院系"], ["信息工程", "OK"]],
}, {
    "cmd": "删除专业",
    "params": ["专业名称"],
    "tags": ["删除", "专业", "教师"],
}]
