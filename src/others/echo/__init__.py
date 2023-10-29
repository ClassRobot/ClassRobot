from nonebot.params import CommandArg
from utils.models import User, Teacher
from nonebot.adapters import Bot, Event, Message
from utils.auth.extension import UserExtension, TeacherExtension
from nonebot_plugin_alconna import Args, Alconna, Extension, AlconnaMatcher, on_alconna

echo = on_alconna(
    "echo", block=True, use_cmd_start=True, extensions=[TeacherExtension()]
)


@echo.handle()
async def _(matcher: AlconnaMatcher, user: Teacher):
    print(user)
    # await matcher.send(message)
