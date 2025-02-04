# from nonebot.adapters.ntchat import FileMessageEvent
from utils import Emoji
from utils.tools import StringCard
from utils.models import Tasks, Classes
from nonebot.params import EventPlainText
from utils.models.annotated import UserDepends, UserOrCreatedDepends
from nonebot_plugin_alconna import File, Image, Other, UniMessage, AlconnaMatcher

from .util import TaskManagerDepends
from .commands import push_task_cmd, query_task_cmd, create_task_cmd, delete_task_cmd


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
            card.text(student.name, student.created_at.strftime("%Y-%m-%d %H:%M:%S"))
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
    if not task_manager:
        await matcher.finish(Emoji.error + "您还未创建任务呢！")
    elif task_name is None:
        await matcher.send(await task_manager.tasks.to_card(Emoji.info + "输入任务ID或名称删除"))
    else:
        matcher.state["got_name"] = UniMessage(task_name)


@delete_task_cmd.got("got_name")
async def _(
    matcher: AlconnaMatcher,
    task_manager: TaskManagerDepends,
    got_name: str = EventPlainText(),
):
    if not (got_name := got_name.strip()):
        await matcher.finish(Emoji.error("任务名称不能为空"))

    if not await task_manager.select(got_name):
        await matcher.finish(Emoji.error(f"没有找到【{got_name}】这个任务"))

    await task_manager.select_task.delete()
    await matcher.finish(Emoji.success(f"“{got_name}”任务删除成功"))


# --------------------------------- 推送任务 ---------------------------------
@push_task_cmd.handle()
async def _(matcher: AlconnaMatcher, task_manager: TaskManagerDepends):
    ...
