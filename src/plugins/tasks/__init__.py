from io import BytesIO

from utils import Emoji
from qrcode import QRCode
from nonebot import logger
from qrcode.image.pil import PilImage
from utils.send import bot_upload_file
from utils.models import Tasks, Classes
from qrcode.image.pure import PyPNGImage
from nonebot.params import Arg, ArgPlainText
from utils.tools import StringCard, text_to_qrcode
from nonebot.adapters import Bot, Event, MessageTemplate
from nonebot_plugin_alconna import UniMessage, AlconnaMatcher
from utils.models.depends import UserDepends, StudentDepends, UserOrCreatedDepends

from .commands import (
    push_task_cmd,
    query_task_cmd,
    create_task_cmd,
    delete_task_cmd,
    export_task_cmd,
)
from .util import (
    TaskFile,
    TaskManager,
    FileDataDepends,
    PushTaskManager,
    TaskManagerDepends,
    task_manager_depends,
)


# --------------------------------- 创建任务 ---------------------------------
@create_task_cmd.handle()
async def _(matcher: AlconnaMatcher, user: UserDepends):
    if user is None:
        await matcher.finish()
    elif user.student:
        matcher.state["classes"] = user.student.classes
        matcher.state["role"] = "student"
    elif user.teacher:
        matcher.state["role"] = "teacher"
        await matcher.finish(Emoji.warning + "教师暂不支持创建")
    else:
        await matcher.finish()


@create_task_cmd.got("classes")
async def _(matcher: AlconnaMatcher, task_name: str, user: UserOrCreatedDepends):
    classes = matcher.state.get("classes")
    if isinstance(classes, Classes):
        if await classes.get_task(task_name):
            await matcher.finish(Emoji.warning + f"“{task_name}”任务已存在，请勿重复创建！")
        await Tasks.create_task(task_name, classes, user, matcher.state["role"])
        await matcher.finish(Emoji.success + f"“{task_name}”任务创建成功")


# --------------------------------- 查询任务 ---------------------------------
@query_task_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    task_name: str | None,
    task_manager: TaskManagerDepends,
):
    # 没有指定任务名称，显示所有任务
    if task_name is None:
        if task_manager:
            await matcher.finish(await task_manager.tasks.to_card())
        await matcher.finish(Emoji.error + "您还未创建任务呢！")
    elif not await task_manager.select(task_name):
        await matcher.finish(Emoji.error + f"没有找到【{task_name}】这个任务")

    # 选择了需要查询的指定任务，显示已提交于未提交的学生
    submitted, not_submitted = await task_manager.commits()
    if not submitted and not not_submitted:
        await matcher.finish(Emoji.warning("您的班级中没有学生"))
    if submitted:  # 已提交的学生
        card = StringCard().hr("已提交")
        for student in submitted:
            card.text(
                student.name,
                student.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                sep=" | ",
            )
        await matcher.send(card.render())
    else:
        await matcher.send(Emoji.warning + "暂无学生提交")
    if not_submitted:  # 未提交的学生
        await matcher.finish(
            Emoji.info(
                "未提交的学生\n%s\n" % (StringCard.h * StringCard.hr_len)
                + " ".join(student.name for student in not_submitted)
            )
        )
    else:
        await matcher.finish(Emoji.success + "所有学生都已提交任务")


# --------------------------------- 删除任务 ---------------------------------
@delete_task_cmd.handle()
async def _(
    matcher: AlconnaMatcher, task_name: str | None, task_manager: TaskManagerDepends
):
    if task_name is None:
        if not task_manager:
            await matcher.finish(Emoji.error + "您还未创建任务呢！")
        await matcher.send(await task_manager.tasks.to_card(Emoji.info + "输入任务ID或名称删除"))
    else:
        matcher.state["got_name"] = UniMessage(task_name)


@delete_task_cmd.got("got_name")
async def _(
    matcher: AlconnaMatcher,
    task_manager: TaskManagerDepends,
    got_name: str = ArgPlainText(),
):
    if not (got_name := got_name.strip()):
        await matcher.finish(Emoji.error("任务名称不能为空"))

    if not await task_manager.select(got_name):
        await matcher.finish(Emoji.error(f"没有找到【{got_name}】这个任务"))

    await task_manager.select_task.delete()
    await matcher.finish(Emoji.success(f"“{got_name}”任务删除成功"))


# --------------------------------- 推送任务 ---------------------------------
@push_task_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    task_arg: tuple,
    task_manager: TaskManager = task_manager_depends("student", PushTaskManager),
):
    for arg in task_arg:
        if isinstance(arg, str) and "task_name" not in matcher.state:
            matcher.state["task_name"] = UniMessage(arg)
        elif isinstance(arg, TaskFile) and "task_file" not in matcher.state:
            matcher.state["task_file"] = UniMessage(arg)

    if not task_manager.submit_tasks:  # 没有填写task_name查看是否有任务
        await matcher.finish(Emoji.error + "您所在的班级还未创建任务呢！")

    if "task_name" not in matcher.state:
        matcher.state["task_list"] = await task_manager.submit_tasks.to_card(
            Emoji.info + "输入任务ID或名称提交"
        )


@push_task_cmd.got("task_name", MessageTemplate("{task_list}"))
async def _(
    matcher: AlconnaMatcher,
    task_manager: PushTaskManager = task_manager_depends("student", PushTaskManager),
    task_name: UniMessage = Arg(),
):
    if task_manager.set_task_file(task_name) and task_manager.task_file:
        # 再次检查是否有文件
        matcher.state["task_file"] = UniMessage(task_manager.task_file)

    task_text = task_name.extract_plain_text()
    if not task_text:
        await matcher.finish(Emoji.error + "任务名称不能为空")
    if not await task_manager.select(task_text):  # 根据任务名称选择任务
        await matcher.finish(Emoji.error + f"没有找到【{task_text}】这个任务")


@push_task_cmd.got("task_file", "文件给我吧！")
async def _(
    matcher: AlconnaMatcher,
    student: StudentDepends,
    file_data: FileDataDepends,
    task_manager: PushTaskManager = task_manager_depends("student", PushTaskManager),
):
    if student is None:
        await matcher.finish(Emoji.error + "您还未加入班级！")
    elif not file_data:
        await matcher.finish(Emoji.error + "未能获取到你提交的文件！")
    elif await task_manager.check_file_exists(file_data.get_data()):
        await matcher.finish(Emoji.error("这个文件已经被提交过了！请不要使用别人的文件哦！"))

    if task_commit := await task_manager.select_task.get_commit(student):
        await task_commit.update_file(file_data.get_data())
        await matcher.finish(Emoji.success + "任务文件更新成功！")
    else:
        await task_manager.select_task.commit(student, file_data.get_data())
        await matcher.finish(Emoji.success + "任务提交成功！")


# --------------------------------- 导出任务 ---------------------------------
@export_task_cmd.handle()
async def _(
    matcher: AlconnaMatcher,
    task_name: str | None,
    task_manager: TaskManagerDepends,
):
    if task_name is None:
        if not task_manager:
            await matcher.finish(Emoji.error + "您还未创建任务呢！")
        await matcher.send(await task_manager.tasks.to_card(Emoji.info + "输入任务ID或名称导出"))
    else:
        matcher.state["got_name"] = UniMessage(task_name)


@export_task_cmd.got("got_name")
async def _(
    bot: Bot,
    event: Event,
    matcher: AlconnaMatcher,
    task_manager: TaskManagerDepends,
    got_name: str = ArgPlainText(),
):
    if not (got_name := got_name.strip()):
        await matcher.finish(Emoji.error("任务名称不能为空"))

    if not await task_manager.select(got_name):
        await matcher.finish(Emoji.error(f"没有找到【{got_name}】这个任务"))

    download_url = await task_manager.build_task()
    if download_url is None:
        await matcher.finish(Emoji.error + "导出失败，可能还没有人提交！")

    await matcher.send(Emoji.info + "打包文件后导出，请稍等...")
    try:
        if not await bot_upload_file(
            bot, event, download_url.split("/")[-1], download_url
        ):
            await matcher.send(UniMessage.file(url=download_url))
    except Exception as e:
        logger.exception(e)
        await matcher.finish(
            UniMessage(Emoji.warning("文件发送失败，可以尝试扫码下载"))
            + UniMessage.image(raw=text_to_qrcode(download_url))
        )
        # await matcher.finish(Emoji.warning("文件发送失败，可以尝试从链接中下载", download_url, sep="\n"))
