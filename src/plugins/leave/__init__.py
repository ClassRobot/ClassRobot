from nonebot_plugin_alconna import Image, AlconnaMatcher

from .commands import leave_cmd
from .depends import AddLeaveDepends


@leave_cmd.handle()
async def _(
    matcher: AlconnaMatcher, leave_reason: list[str | Image], add_leave: AddLeaveDepends
):
    print(leave_reason)
    if leave := await add_leave.send_message(leave_reason):
        await matcher.finish(leave.reply)
