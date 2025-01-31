# from nonebot.adapters.ntchat import FileMessageEvent
from utils import alias_product
from nonebot_plugin_alconna import File, Image, Other

from .commands import push_task_cmd


@push_task_cmd.handle()
async def _(file: Image | File | Other):
    if isinstance(file, Image):
        print(file.url)
    elif isinstance(file, File):
        print(file.url)
    elif isinstance(file, Other) and file.origin and file.origin.type == "file":
        print(file.origin.data)
    else:
        print(file)
