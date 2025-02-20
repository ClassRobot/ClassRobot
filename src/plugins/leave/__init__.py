from nonebot_plugin_alconna import Image, UniMsg, AlconnaMatcher, UniMessage

from utils import Emoji

from .commands import add_leave_cmd, query_leave_cmd, delete_leave_cmd
from .depends import AddLeaveDepends, QueryLeaveDepends

# --------------------------------- 添加请假 ---------------------------------


@add_leave_cmd.handle()
async def _(
    matcher: AlconnaMatcher, leave_reason: list[str | Image], add_leave: AddLeaveDepends
):
    add_leave.add_message(leave_reason)  # 将消息保存
    if add_leave.image_url:  # 查看用户消息是否有添加图片
        matcher.state["leave_image"] = UniMessage.image(url=add_leave.image_url)


@add_leave_cmd.got(
    "leave_image", prompt=Emoji.warning + "您还要发一张请假截图证明呢！"
)  # 未添加则提示
async def _(matcher: AlconnaMatcher, msg: UniMsg, add_leave: AddLeaveDepends):
    add_leave.add_message(msg)  # 再次保存内容
    if not add_leave.image_url:  # 如果二次没有提交则退出程序
        await matcher.finish(Emoji.error + "未能拿到您的证明图片，请重试！")

    if leave := await add_leave.send_message():
        student_leave = await add_leave.save_student_leave(leave)
        await matcher.send(Emoji.success + leave.reply)
        await add_leave.notice_leave(student_leave)
    else:
        await matcher.finish(Emoji.error + "请假提交失败！")


# --------------------------------- 请假列表 ---------------------------------


@query_leave_cmd.handle()
async def _(matcher: AlconnaMatcher, query_leave: QueryLeaveDepends):
    if query_leave.is_classes_admin:
        leave_list = await query_leave.get_classes_leave()
    elif query_leave.is_student:
        leave_list = await query_leave.get_student_leave()

    if leave_list:
        for msg in query_leave.leave_to_messages(leave_list):
            await matcher.send(msg)

    await matcher.finish(Emoji.error + "您没有可查询请假条")


# --------------------------------- 删除请假 ---------------------------------
@delete_leave_cmd.handle()
async def _(
    matcher: AlconnaMatcher, leave_id: list[str], query_leave: QueryLeaveDepends
):
    leave_list = None
    leave_ids = [int(leave_id) for leave_id in leave_id]
    if not leave_ids:
        await matcher.finish(Emoji.error + "请输入要删除的请假条ID")

    if query_leave.is_classes_admin:
        leave_list = await query_leave.get_classes_leave()
    elif query_leave.is_student:
        leave_list = await query_leave.get_student_leave()

    # 如果没有请假条则直接返回
    if leave_list is None:
        await matcher.finish(Emoji.error + "您没有可删除的请假条")

    # 删除请假条
    for leave in leave_list:
        if leave.id in leave_ids:
            await leave.filter(id=leave.id).delete()

    await matcher.finish(Emoji.success + "删除成功！")
