from nonebot.adapters import Event
from nonebot_plugin_alconna.model import CompConfig
from nonebot_plugin_alconna import At, UniMessage, AlconnaMatcher, on_alconna

from .alconna import add_teacher_alc

add_teacher = on_alconna(
    add_teacher_alc,
    block=True,
    comp_config=CompConfig(
        lite=False,
        disables={"tab", "enter", "exit"},
    ),
)


@add_teacher.handle()
async def _(name: str, phone: int, matcher: AlconnaMatcher, at: At | str, event: Event):
    print(event.get_user_id())

    if isinstance(at, At):
        print(at.target)
    else:
        print(at)
    await matcher.finish(UniMessage(f"{name} {phone}"))
