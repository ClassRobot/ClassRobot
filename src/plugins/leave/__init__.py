from nonebot_plugin_alconna import Image, UniMsg, AlconnaMatcher

from .commands import leave_cmd
from .depends import AddLeaveDepends


@leave_cmd.handle()
async def _(
    matcher: AlconnaMatcher, leave_reason: list[str | Image], add_leave: AddLeaveDepends
):
    print(leave_reason)
    add_leave.add_message(leave_reason)
    if add_leave.image_url:
        matcher.state["leave_image"] = add_leave.image_url


@leave_cmd.got("leave_image", prompt="您还要发一张请假截图证明呢！")
async def _(matcher: AlconnaMatcher, msg: UniMsg):
    ...
