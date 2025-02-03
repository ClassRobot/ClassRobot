# from nonebot.adapters.ntchat import FileMessageEvent
from utils import Emoji
from utils.tools import StringCard
from utils.models import Tasks, Classes
from utils.models.annotated import UserDepends, UserOrCreatedDepends
from nonebot_plugin_alconna import File, Image, Other, AlconnaMatcher

from .util import TaskManagerDepends
from .commands import query_task_cmd, create_task_cmd


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
        await matcher.finish(Emoji.warning + "您的班级中没有学生")
    if submitted:
        card = StringCard().hr("已提交")
        for student in submitted:
            card.text(student.name, student.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        await matcher.send(card.render())
    else:
        await matcher.send(Emoji.warning + "暂无学生提交")
    if not_submitted:
        await matcher.finish(
            "未提交学生\n" + " ".join(student.name for student in not_submitted)
        )
    else:
        await matcher.finish(Emoji.success + "所有学生都已提交任务")
