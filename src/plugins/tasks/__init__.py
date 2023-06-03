from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Message, MessageSegment, Bot, MessageEvent
from nonebot.params import CommandArg, Arg
from nonebot.matcher import Matcher

from utils.orm import Student
from utils.manages import USER, User, STUDENT
from utils.tools import upload_file

from .commands import add_task, del_task, show_task, push_task, export_task, clear_task, __helper__
from .methods import AddTask, ClearTask, DelTask, ExportTask, PushTask, ShowTask


# --------------------------------- 添加任务 ---------------------------------
@add_task.handle()
async def _(matcher: Matcher, msg: Message = CommandArg(), _: User = USER):
    if text := msg.get("text"):
        matcher.set_arg("task_title", text)


@add_task.got("task_title", prompt="任务名字叫什么呢？")
async def _(matcher: Matcher, state: T_State, task_title: Message = Arg()):
    title: str = task_title.extract_plain_text().strip()
    task = AddTask(state["user"])
    if warn := task.check_task_name(title):
        await matcher.finish(warn)
    else:
        student: Student = state["user"]
        if task.is_student:
            if class_task := await task.add_task(title, student.class_table):
                await matcher.finish(f"OK,任务ID：{class_task.id}")
            await matcher.finish("似乎重名了！")
        else:
            state["task_title"] = title
            state["task"] = task
            if task.teacher_class.exists():
                await matcher.send("需要添加到哪个班级呢？\n" + await task.teacher_class_names())
            else:
                await matcher.finish("你还没创建过班级呢！")


# 当如果是教师身份则会进入选择班级阶段
@add_task.got("class_name")
async def _(matcher: Matcher, state: T_State, class_name: Message = Arg()):
    task: AddTask = state["task"]
    if class_table := await task.select_class(class_name.extract_plain_text()):
        if class_task := await task.add_task(
            state["task_title"], 
            class_table=class_table
        ):
            await matcher.finish(f"OK,任务ID：{class_task.id}")
        await matcher.finish("似乎重名了！")
    else:
        await matcher.finish("没有这个班级，你是不是写错了？")


# --------------------------------- 删除任务 ---------------------------------
@del_task.handle()
async def _(state: T_State, matcher: Matcher, msg: Message = CommandArg(), user: User = USER):
    task = DelTask(user)
    state["task"] = task
    if not await task.exists():
        await matcher.finish("还没有创建过任务哦！")
    elif title := msg.get("text"):
        matcher.set_arg("task_title", title)
    else:
        await matcher.send(
            MessageSegment.image(
                await task.tasks_to_image("请输入您要删除的任务的ID")
            )
        )


@del_task.got("task_title")
async def _(matcher: Matcher, task_title: Message = Arg()):
    if task_title.get("text"):
        await matcher.send("要删除的话请发送'确认'")
    else:
        await matcher.finish("不说算了！")


@del_task.got("is_del")
async def _(matcher: Matcher, state: T_State, is_del: Message = Arg()):
    task: DelTask = state["task"]
    if is_del.extract_plain_text() == "确认":
        if await task.del_task(state["task_title"].extract_plain_text()):
            await matcher.finish("OK")
        await matcher.finish("没有这个任务")
    await matcher.finish("中止了！")


# --------------------------------- 查询任务 ---------------------------------
@show_task.handle()
async def _(matcher: Matcher, msg: Message = CommandArg(), user: User = USER):
    task = ShowTask(user)
    if not await task.exists():
        await matcher.finish("还没有创建过任务哦！")
    elif text := msg.extract_plain_text():
        async for v in task.show_task(text):
            await matcher.send(v)
    else:
        await matcher.finish(
            MessageSegment.image(
                await task.tasks_to_image()
            )
        )


# --------------------------------- 提交任务 ---------------------------------
@push_task.handle()
async def _(matcher: Matcher, state: T_State, msg: Message = CommandArg(), user: Student = STUDENT):
    task = PushTask(user)
    state["task"] = task
    task.save_file.add_file(msg)
    if not await task.exists():
        await matcher.finish("还没有创建过任务哦！")
    elif text := msg.get("text"):
        matcher.set_arg("task_msg", text)
    else:
        await matcher.send(
            MessageSegment.image(
                await task.tasks_to_image("输入需要提交的任务ID")
            )
        )


@push_task.got("task_msg")
async def _(matcher: Matcher, state: T_State, task_msg: Message = Arg()):
    task: PushTask = state["task"]
    if task.save_file.add_file(task_msg) and not task_msg.extract_plain_text():   
        # 继续尝试往任务内添加图片
        await matcher.reject("是要交到哪个任务？")
    if task.save_file.file_exists:
        # 图片存在则不询问图片
        matcher.set_arg("images", Message())


@push_task.got("images", prompt="图呢？")
async def _(matcher: Matcher, state: T_State, task_msg: Message = Arg("task_msg")):
    task: PushTask = state["task"]
    task.save_file.add_file(state["images"])
    if (text := task_msg.extract_plain_text()) and task.save_file.file_exists:
        await matcher.finish(await task.push_task(text))
    else:
        await matcher.finish("提交失败了！")


# --------------------------------- 导出任务 ---------------------------------
@export_task.handle()
async def _(matcher: Matcher, state: T_State, msg: Message = CommandArg(), user: User = USER):
    task = ExportTask(user)
    state["task"] = task
    if not await task.exists():
        await matcher.finish("还没有创建过任务哦！")
    elif text := msg.get("text"):
        matcher.set_arg("task_title", text)
    else:
        await matcher.send(
            MessageSegment.image(
                await task.tasks_to_image("需要导出哪个任务")
            )
        )


@export_task.got("task_title")
async def _(event: MessageEvent, state: T_State, task_title: Message = Arg()):
    task: ExportTask = state["task"]
    if title := task_title.extract_plain_text():
        async for filepath, filename in task.export_task(title):
            await upload_file(event, filepath, filename)
            await task.delete_zip_file(filepath)


# --------------------------------- 清空任务 ---------------------------------
@clear_task.handle()
async def _(matcher: Matcher, state: T_State, msg: Message = CommandArg(), user: User = USER):
    task = ClearTask(user)
    state["task"] = task
    if isinstance(user, Student):   # 学生进行删除
        if not await task.clear_task(user.class_table):
            await matcher.finish("OK,但似乎有文件被占用没有彻底删除，可以稍后重试！")
        await matcher.finish("OK")
    elif text := msg.get("text"):   # 教师清除时会选择班级
        matcher.set_arg("class_name", text)
    else:
        await matcher.send(
            "要清空哪个呢？\n" + (
                "\n".join(
                    f"{i}.{v}" for i, v in enumerate(
                        [i.name async for i in task.teacher_class]
                    )
                )
            )
        )


@clear_task.got("class_name")
async def _(matcher: Matcher, state: T_State, class_name: Message = Arg()):
    task: ClearTask = state["task"]
    if class_table := await task.select_class(class_name.extract_plain_text()):
        if not await task.clear_task(class_table):
            await matcher.finish("OK,但似乎有文件被占用没有彻底删除，可以稍后重试！")
        await matcher.finish("OK")


