from nonebot_plugin_alconna import AlconnaMatcher

from .commands import add_classes_curriculum


@add_classes_curriculum.handle()
async def _(matcher: AlconnaMatcher):
    pass
