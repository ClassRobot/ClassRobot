# from nonebot.adapters.ntchat import FileMessageEvent
from utils import alias_product
from utils.tools import StringCard
from utils.models import Tasks, Classes
from utils.models.annotated import UserDepends, UserOrCreatedDepends
from nonebot_plugin_alconna import File, Image, Other, AlconnaMatcher

from .util import TaskManager
from .commands import query_task_cmd, create_task_cmd


# --------------------------------- 创建任务 ---------------------------------
@create_task_cmd.handle()
async def _(matcher: AlconnaMatcher, task_name: str, user: UserDepends):
    print(task_name)
    if user is None:
        await matcher.finish()
    elif user.student:
        matcher.state["classes"] = user.student.classes
        matcher.state["role"] = "student"
    elif user.teacher:
        matcher.state["role"] = "teacher"
        await matcher.finish("教师暂不支持创建")
    else:
        await matcher.finish()


@create_task_cmd.got("classes")
async def _(matcher: AlconnaMatcher, task_name: str, user: UserOrCreatedDepends):
    classes = matcher.state.get("classes")
    if isinstance(classes, Classes):
        if await classes.get_task(task_name):
            await matcher.finish(f"“{task_name}”任务已存在，请勿重复创建！")
        await Tasks.create_task(task_name, classes, user, matcher.state["role"])
        await matcher.finish(f"“{task_name}”任务创建成功")


# --------------------------------- 查询任务 ---------------------------------
@query_task_cmd.handle()
async def _(matcher: AlconnaMatcher, task_name: str | None, user: UserOrCreatedDepends):
    task_manager = TaskManager()
    if user.student:
        task_manager.add_task(*user.student.classes.tasks)
    if user.teacher:
        for classes in user.teacher.classes:
            task_manager.add_task(*classes.tasks)

    if task_manager:
        await matcher.finish("您还未创建任务呢！")

    # 没有指定任务名，返回所有任务
    if not task_name:
        await matcher.finish(task_manager.tasks_string())

    # 指定任务名，返回任务详情
    submitted, not_submitted = task_manager.commits(task_name)
    if submitted:
        card = StringCard().hr("已提交的学生")
        for student in submitted:
            card.text(student.name, student.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        await matcher.send(card.render())
    else:
        await matcher.send("没有学生提交任务")
    await matcher.finish(
        " ".join(student.name for student in not_submitted)
        if not_submitted
        else "所有学生都已提交任务"
    )
