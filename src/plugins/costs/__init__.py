from utils.orm import Student
from utils.auth import USER, User
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.params import Arg, CommandArg
from utils.tools import MessageArgs, upload_file
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment

from .methods import AddCost, ShowCost, ExportCost
from .commands import add_cost, show_cost, __helper__, export_cost


# --------------------------------- 添加班费 ---------------------------------
@add_cost.handle()
async def _(
    matcher: Matcher, state: T_State, msg: Message = CommandArg(), user: User = USER
):
    state["cost"] = AddCost(user)
    state["args"] = MessageArgs(
        {"fee_type": "是用来做什么了", "fee_money": "花费多少（元）"}, matcher
    )
    if text := msg.get("text"):
        matcher.set_arg("msg", text)


@add_cost.got("msg", prompt="是用来做什么了？花费多少？")
async def _(matcher: Matcher, state: T_State, msg: Message = Arg()):
    if text := msg.extract_plain_text().split():
        values: dict = await state["args"](text)
        cost: AddCost = state["cost"]
        if not cost.is_number(values["fee_money"]):
            await matcher.finish("费用只能是数字")
        elif cost.is_student:
            class_cost = await cost.add_cost(**values)
            await matcher.finish(MessageSegment.image(await cost.to_card(class_cost)))
        else:
            if len(text) > 2:
                matcher.set_arg("class_name", Message(text[3]))
            else:
                await matcher.send(f"是哪个班级的支出呢？\n{await cost.teacher_class_names()}")


@add_cost.got("class_name")
async def _(matcher: Matcher, state: T_State, class_name: Message = Arg()):
    cost: AddCost = state["cost"]
    if name := class_name.extract_plain_text():
        if class_table := await cost.select_class(name):
            class_cost = await cost.add_cost(
                **state["args"].kwargs, class_table=class_table
            )
            await matcher.finish(MessageSegment.image(await cost.to_card(class_cost)))
        await matcher.finish("没有这个班级！")
    await matcher.finish("不说算了！")


# --------------------------------- 查询班费 ---------------------------------
@show_cost.handle()
async def _(
    matcher: Matcher, state: T_State, msg: Message = CommandArg(), user: User = USER
):
    cost = ShowCost(user)
    state["cost"] = cost
    text = msg.extract_plain_text()
    cost.set_date(text)
    if isinstance(user, Student):
        if costs := await cost.show_cost(user.class_table):
            await matcher.finish(MessageSegment.image(costs))
        else:
            await matcher.finish("还没有记录！")
    elif await cost.teacher_class_count():
        await matcher.send("看哪个班呢？\n" + await cost.teacher_class_names())
    else:
        await matcher.finish("您还没有班级哦！")


@show_cost.got("class_name")
async def _(matcher: Matcher, state: T_State, class_name: Message = Arg()):
    cost: ShowCost = state["cost"]
    if name := class_name.extract_plain_text():
        if class_table := await cost.select_class(name):
            if costs := await cost.show_cost(class_table):
                await matcher.finish(MessageSegment.image(costs))
            await matcher.finish("还没有记录！")
        await matcher.finish("没有这个班级！")
    await matcher.finish("不说算了")


# --------------------------------- 导出班费 ---------------------------------
@export_cost.handle()
async def _(
    matcher: Matcher,
    event: MessageEvent,
    state: T_State,
    msg: Message = CommandArg(),
    user: User = USER,
):
    cost = ExportCost(user)
    cost.set_date(msg.extract_plain_text())
    state["cost"] = cost
    if isinstance(user, Student):
        file_path = await cost.export_cost(user.class_table)
        await upload_file(event, file_path, file_path.name)
        await cost.clear_file(file_path.parent)
        await matcher.finish()
    elif await cost.teacher_class_count():
        await matcher.send("导出哪个班呢？\n" + await cost.teacher_class_names())
    else:
        await matcher.finish("您还没有班级哦！")


@export_cost.got("class_name")
async def _(
    matcher: Matcher, event: MessageEvent, state: T_State, class_name: Message = Arg()
):
    cost: ExportCost = state["cost"]
    if name := class_name.extract_plain_text():
        if class_table := await cost.select_class(name):
            file_path = await cost.export_cost(class_table)
            await upload_file(event, file_path, file_path.name)
            await cost.clear_file(file_path.parent)
            await matcher.finish()
        await matcher.finish("没有这个班级！")
    await matcher.finish("不说算了")
