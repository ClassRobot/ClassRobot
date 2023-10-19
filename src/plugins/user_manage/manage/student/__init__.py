from re import findall
from pathlib import Path

from nonebot import on_command
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from utils.params import DocsUrlParams
from utils.auth import TEACHER, CLASS_TABLE
from utils.tools import MessageArgs, upload_file
from nonebot_plugin_orm import select, get_session
from nonebot.params import CommandArg, ArgPlainText
from utils.models import Student, Teacher, ClassTable
from utils.tools.docs_sheet import GetDocsSheet, InitialAttributedTextError
from nonebot.adapters.onebot.v11 import Message, MessageEvent, GroupMessageEvent

from .method import AddStudent, BatchImportStudents, base_info

add_args = {v: k for k, v in base_info.items()}
add_student = on_command("添加学生", aliases={"新增学生", "增加学生"}, priority=100, block=True)
post_student = on_command("导入学生", aliases={"导入班级"}, priority=100, block=True)
del_student = on_command("删除学生", aliases={"移除学生"}, priority=100, block=True)
student_excel = on_command("获取导入表格", priority=100, block=True)


# --------------------------------- 添加学生 ---------------------------------
@add_student.handle()
async def _(
    matcher: Matcher,
    state: T_State,
    event: GroupMessageEvent,
    msg: Message = CommandArg(),
    teacher: Teacher = TEACHER,
    class_table: ClassTable = CLASS_TABLE,
):
    if class_table.teacher == teacher.id:
        state["class_table"] = class_table
        state["args"] = MessageArgs(add_args, matcher, "说一下“{}”")
        state["params"] = msg
    else:
        await matcher.finish("这不是班级群，无法添加学生！")


@add_student.got("params")
async def _(
    matcher: Matcher, _: GroupMessageEvent, state: T_State, params: str = ArgPlainText()
):
    info = await state["args"](params)
    add_student = AddStudent(info)
    try:
        await add_student.insert(state["teacher"], state["class_table"])
    except ValueError as err:
        key = findall(r"Field '(.*?)' expected", str(err))[-1]
        await matcher.finish(f"{add_args[key]}写错了呢！")
    except IntegrityError:
        await matcher.finish("好像已经存在了呢！")
    else:
        await matcher.finish("OK")


# --------------------------------- 批量导入学生 ---------------------------------
@post_student.handle()
async def _(
    state: T_State,
    matcher: Matcher,
    event: GroupMessageEvent,
    msg: Message = CommandArg(),
    teacher: Teacher = TEACHER,
):
    if class_table := await ClassTable.objects.filter(
        group_id=event.group_id, teacher=teacher
    ).afirst():
        state["class_table"] = class_table
        if msg:
            state["params"] = msg
    else:
        await matcher.finish("这不是班级群，无法导入学生噢！")


@post_student.got("params", prompt="请发一下腾讯在线表格链接吧！")
async def _(state: T_State, matcher: Matcher, url: str = DocsUrlParams):
    try:
        if sheet := await GetDocsSheet(url):
            bis = BatchImportStudents(sheet.data)
            if columns := bis.check_base_columns():
                await matcher.finish("缺少所需的列：" + (",".join(columns)))
            elif not (missing := bis.check_missing_value()).empty:
                await matcher.finish(
                    ",".join(str(i) for i in missing.index + 1) + "有东西没写！"
                )
            await bis.insert(state["teacher"], state["class_table"])
            await matcher.finish("OK")
    except InitialAttributedTextError:
        await matcher.finish("看不到表格里的东西，是不是设置了权限？？")


# --------------------------------- 删除学生 ---------------------------------
@del_student.handle()
async def _(state: T_State, msg: Message = CommandArg(), _: Teacher = TEACHER):
    if text := msg.get("text"):
        state["text"] = text


@del_student.got("text", prompt="qq是多少呢？")
async def _(state: T_State, matcher: Matcher, text: str = ArgPlainText()):
    if all_id := [int(i) for i in text.split() if i.isdigit()]:
        teacher: Teacher = state["teacher"]
        if (await Student.objects.filter(teacher=teacher, qq__in=all_id).adelete())[
            0
        ]:  # 学生qq
            await matcher.finish("OK")
        await matcher.finish("没有这位学生呢！")


# --------------------------------- 导入表格 ---------------------------------
@student_excel.handle()
async def _(event: MessageEvent):
    await upload_file(event, Path(__file__).parent / "base_excel.xlsx", "基本表格.xlsx")


__helper__ = [
    {
        "cmd": "添加学生",
        "alias": ["新增学生", "增加学生"],
        "params": list(base_info.keys()),
        "tags": ["添加", "学生", "教师"],
        "doc": "需要在自己的班级群内进行添加学生，然后填写对应参数，可以依次慢慢输入，并不一定要合并在一起输入，但顺序不能错误",
    },
    {
        "cmd": "导入学生",
        "alias": ["导入班级"],
        "params": ["腾讯文档在线表格链接"],
        "tags": ["导入", "添加", "教师", "学生"],
        "doc": "批量导入学生信息【必须是使用腾讯在线文档表格】，其它文档不支持！\n如果您不知道表格格式，你可以发送【获取导入表格】",
    },
    {
        "cmd": "删除学生",
        "alias": ["移除学生"],
        "params": ["学生qq"],
        "tags": ["移除", "学生", "教师", "删除"],
    },
    {
        "cmd": "获取导入表格",
        "tags": ["导入", "获取", "表格", "学生", "教师"],
        "doc": "机器人会发送导入学生的表格，将表格转为腾讯文档在线表格，然后将学生信息填写进去就可以",
    },
]
