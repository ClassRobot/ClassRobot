from nonebot import on_command
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, Arg
from nonebot.adapters.onebot.v11 import Message

from utils.orm import Student, Teacher
from utils.tools import MessageArgs
from utils.manages import User, USER, TEACHER

from .config import ModifiableColumns

set_password = on_command("修改密码", aliases={"设置密码", "重置密码"}, priority=100, block=True)
set_student = on_command("修改学生", aliases={"修改学生信息"}, priority=100, block=True)
set_user = on_command("修改信息", aliases={"修改内容"}, priority=100, block=True)


# --------------------------------- 修改密码 ---------------------------------
@set_password.handle()
async def _(matcher: Matcher, msg: Message = CommandArg(), user: User = USER):
    await Student.objects.filter(qq=user.qq).afirst()
    if text := msg.extract_plain_text():
        # user.password = text
        user.save()
        await matcher.finish("OK")


# --------------------------------- 修改学生信息 ---------------------------------
@set_student.handle()
async def _(
    matcher: Matcher, state: T_State, msg: Message = CommandArg(), _: Teacher = TEACHER
):
    state["args"] = MessageArgs(
        {
            "user": "",
            "key": "你可以修改:%s" % " ".join(ModifiableColumns.teacher_modifiable.keys()),
            "value": "改成什么呢？",
        },
        matcher,
    )
    if text := msg.get("text"):
        matcher.set_arg("params", text)


@set_student.got("params", prompt="你需要修改的学生的QQ")
async def _(matcher: Matcher, state: T_State, params: Message = Arg()):
    info: dict = await state["args"](params.extract_plain_text())
    if key := ModifiableColumns.teacher_modifiable.get(info["key"]):
        if student := await Student.objects.filter(
            qq=info["user"], teacher=state["teacher"]
        ).afirst():
            raw = getattr(student, key)
            if isinstance(raw, int):
                if not info["value"].isdigit():
                    await matcher.finish("你这个应该用数字表示")
                info["value"] = int(info["value"])
            setattr(student, key, info["value"])
            student.save()
            await matcher.finish(f"“{raw}”修改为“{info['value']}”")
        else:
            await matcher.finish("您没有这个学生！！")
    else:
        await matcher.finish(f"没有“{info['key']}”可以修改！")


# --------------------------------- 修改其它信息 ---------------------------------
@set_user.handle()
async def _(
    matcher: Matcher, state: T_State, msg: Message = CommandArg(), user: User = USER
):
    state["args"] = MessageArgs({"key": "", "value": "改成什么呢？"}, matcher)
    state["mc"] = (
        ModifiableColumns.student
        if isinstance(user, Student)
        else ModifiableColumns.teacher
    )
    if text := msg.get("text"):
        matcher.set_arg("params", text)
    else:
        await matcher.send("你可以改：%s" % " ".join(state["mc"].keys()))


@set_user.got("params")
async def _(matcher: Matcher, state: T_State, params: Message = Arg()):
    info: dict = await state["args"](params.extract_plain_text())
    user: User = state["user"]
    if key := state["mc"].get(info["key"]):
        raw = getattr(user, key)
        if isinstance(raw, int):
            if not info["value"].isdigit():
                await matcher.finish("你这个应该用数字表示")
            info["value"] = int(info["value"])
        await matcher.send(f"确定要将“{raw}”修改为“{info['value']}”吗？")
        setattr(user, info["key"], info["value"])
    else:
        await matcher.finish(f"没有“{info['key']}”可以修改！")


@set_user.got("is_ok")
async def _(matcher: Matcher, state: T_State, is_ok: Message = Arg()):
    if is_ok.extract_plain_text() in ["确定", "确认"]:
        state["user"].save()
        await matcher.finish("OK")
    else:
        await matcher.finish("已经取消了")


__helper__ = [
    {
        "cmd": "修改密码",
        "alias": ["重置密码", "设置密码"],
        "params": ["新密码"],
        "tags": ["修改", "密码", "教师", "学生"],
    },
    {
        "cmd": "修改信息",
        "alias": ["修改内容"],
        "params": ["需要修改的", "修改的信息"],
        "tags": ["修改", "学生", "教师"],
        "use": [
            ["修改信息 联系方式", "改成什么呢？"],
            ["114514", "您确定要将'123456'修改成'114514'吗？"],
            ["确认", "OK"],
        ],
        "doc": "修改自己的某项信息。",
    },
    {
        "cmd": "修改学生",
        "alias": ["修改学生信息"],
        "params": ["学生QQ", "需要修改的", "修改的信息"],
        "tags": ["修改", "学生", "教师"],
        "use": [["修改信息 123456 职位", "改成什么呢？"], ["班长", "'学生'修改成'班长'"]],
        "doc": "可以修改的学生信息有%s" % " ".join(ModifiableColumns.teacher_modifiable.keys()),
    },
]
