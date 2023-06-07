from nonebot import on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.params import CommandArg, Arg
from nonebot.matcher import Matcher

from utils.tools import upload_file
from utils.auth import STUDENT, USER, User
from utils.orm import Student

from .commands import add_moral, export_moral, __helper__
from .methods import AddMoral, ExportMoral


# --------------------------------- 添加德育 ---------------------------------
@add_moral.handle()
async def _(
    matcher: Matcher,
    state: T_State,
    msg: Message = CommandArg(),
    student: Student = STUDENT,
):
    moral = AddMoral(student)
    moral.save_file.add_file(msg)
    state["moral"] = moral
    if text := msg.extract_plain_text().strip():
        if not moral.is_cadre:
            await matcher.finish("您不是干部，不能通过名字向自己或别人添加！！！")
        await moral.set_add_user(text)


@add_moral.got("params", "是做什么事呢？")
async def _(matcher: Matcher, state: T_State, params: Message = Arg()):
    moral: AddMoral = state["moral"]
    moral.save_file.add_file(params)
    if moral.set_text(params.extract_plain_text().strip()):
        if moral.save_file.file_exists:
            await matcher.finish(await moral.add_moral() + " 添加成功")
    else:
        await matcher.finish("不说算了")


@add_moral.got("image", "图呢？")
async def _(matcher: Matcher, state: T_State, image: Message = Arg()):
    moral: AddMoral = state["moral"]
    moral.save_file.add_file(image)
    if moral.save_file.file_exists:
        await moral.add_moral()
        await matcher.finish("OK")
    await matcher.finish("不发图就算了！")


# --------------------------------- 导出德育 ---------------------------------
@export_moral.handle()
async def _(
    matcher: Matcher,
    state: T_State,
    event: MessageEvent,
    msg: Message = CommandArg(),
    user: User = USER,
):
    moral = ExportMoral(user)
    if isinstance(user, Student):
        await upload_file(
            event,
            await moral.export_moral(
                user.class_table, msg.extract_plain_text().strip()
            ),
        )
        await matcher.finish()
    state["moral"] = moral
    state["export_date"] = msg
    await matcher.send("选择导出哪个班级呢？\n" + await moral.teacher_class_names())


@export_moral.got("class_name")
async def _(
    matcher: Matcher, state: T_State, event: MessageEvent, class_name: Message = Arg()
):
    moral: ExportMoral = state["moral"]
    if text := class_name.extract_plain_text().strip():
        if class_table := await moral.select_class(text):
            await upload_file(
                event,
                await moral.export_moral(
                    class_table, state["export_date"].msg.extract_plain_text().strip()
                ),
            )
            await matcher.finish()
        await matcher.finish("没有这个班级")
    await matcher.finish("不说算了！")
