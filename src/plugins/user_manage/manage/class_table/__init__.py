from nonebot import on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Message, GroupMessageEvent
from nonebot.params import CommandArg, ArgPlainText
from nonebot.matcher import Matcher

from utils.tools import MessageArgs
from utils.orm import Teacher, ClassTable, Major
from utils.manages import TEACHER

add_class = on_command("添加班级", priority=100, block=True)
del_class = on_command("删除班级", priority=100, block=True)


# --------------------------------- 添加班级 ---------------------------------
@add_class.handle()
async def _(matcher: Matcher, state: T_State, event: GroupMessageEvent, msg: Message = CommandArg(), _: Teacher = TEACHER):
    if class_table := await ClassTable.objects.filter(group_id=event.group_id).afirst():
        await matcher.finish(f"已经是{class_table.name}班级群咯，不能再改了。")
    else:
        state["args"] = MessageArgs({"class_name": "班级名称", "major": "专业名称"}, matcher)
        if text := msg.get("text"):
            state["params"] = text


@add_class.got("params", prompt="请说一下班级名称、专业名称")
async def _(state: T_State, event: GroupMessageEvent, matcher: Matcher, params: str = ArgPlainText()):
    major_name = (await state["args"](params))["major"]
    if major := await Major.objects.filter(major=major_name).afirst():
        try:
            await ClassTable.objects.acreate(
                class_name=params, 
                group_id=event.group_id, 
                major=major, 
                college=major.college,
                teacher=state["teacher"])
            await matcher.finish("OK")
        except InterruptedError:
            await matcher.finish("这个班级似乎已经存在了！！")
    else:
        await matcher.finish(f"{major_name}这个专业好像不存在！！")


# --------------------------------- 删除班级 ---------------------------------
@del_class.handle()
async def _(state: T_State, matcher: Matcher, msg: Message = CommandArg(), teacher: Teacher = TEACHER):
    state["all_class"] = ClassTable.objects.filter(teacher=teacher)
    if text := msg.get("text"):
        state["params"] = text
    elif state["all_class"]:
        await matcher.send("要删掉哪个呢？\n" + ("\n".join(i.name for i in state["all_class"])))
    else:
        await matcher.finish("您还没有班级！")


@del_class.got("params")
async def _(state: T_State, matcher: Matcher, params: str = ArgPlainText()):
    if params:
        await state["all_class"].filter(class_name=params).adelete()
        await matcher.finish("OK")
    await matcher.finish("不说算了！")


__helper__ = [{
    "cmd": "添加班级",
    "tags": ["添加", "班级", "教师"],
    "use": [["添加班级", "请说一下班级名称、专业名称"], ["人工智能2101 信息工程", "OK"]],
    "doc": "只有教师身份才能添加班级",
    "params": ["班级名称", "专业名称"]
}, {
    "cmd": "删除班级",
    "tags": ["删除", "班级", "教师"],
    "use": [["删除班级", "要删掉哪个呢？\n人工智能2101"], ["人工智能2101", "OK"]],
    "doc": "只能删除自己创建的班级",
    "params": ["班级名称"]
}]



