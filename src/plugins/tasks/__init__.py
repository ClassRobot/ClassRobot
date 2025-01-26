# from nonebot.adapters.ntchat import FileMessageEvent
from utils.config import comp_config
from nonebot_plugin_alconna import Args, File, Field, Image, Other, Alconna, on_alconna

task_cmd = on_alconna(
    Alconna(
        "任务", Args["file", Image | File | Other, Field(completion=lambda: "发送文件给我吧")]
    ),
    aliases={"任务"},
    priority=100,
    block=True,
    comp_config=comp_config,
)


@task_cmd.handle()
async def _(file: Image | File | Other):
    if isinstance(file, Image):
        print(file.url)
    elif isinstance(file, File):
        print(file.url)
    elif isinstance(file, Other) and file.origin and file.origin.type == "file":
        print(file.origin.data)
    else:
        print(file)
