# from nonebot.adapters.ntchat import FileMessageEvent
from utils import alias_product
from utils.models import Tasks, Classes
from utils.models.annotated import UserDepends, UserOrCreatedDepends
from nonebot_plugin_alconna import File, Image, Other, AlconnaMatcher

from .commands import create_task_cmd


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
    else:
        await matcher.finish()


@create_task_cmd.got("classes")
async def _(matcher: AlconnaMatcher, task_name: str, user: UserOrCreatedDepends):
    classes = matcher.state.get("classes")
    if isinstance(classes, Classes):
        await Tasks.create_task(task_name, classes, user, matcher.state["role"])
        await matcher.finish(f"“{task_name}”任务创建成功")
