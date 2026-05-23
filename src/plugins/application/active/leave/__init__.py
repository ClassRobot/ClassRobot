from src.shared import Emoji
from src.platform.commands.params import ArgUniMessage
from nonebot_plugin_alconna import Image, UniMessage, AlconnaMatcher

from .depends import AddLeaveDepends, QueryLeaveDepends
from .commands import add_leave_cmd, query_leave_cmd, delete_leave_cmd

# --------------------------------- 添加请假 ---------------------------------


@add_leave_cmd.handle()
async def _(matcher: AlconnaMatcher, leave_reason: list[str | Image], add_leave: AddLeaveDepends):
    """处理当前命令或事件逻辑。"""
    print(leave_reason)
    add_leave.add_message(leave_reason)  # 将消息保存
    if add_leave.image_url:  # 查看用户消息是否有添加图片
        matcher.state["leave_image"] = UniMessage.image(url=add_leave.image_url)


@add_leave_cmd.got("leave_image", prompt=Emoji.warning + "您还要发一张请假截图证明呢！")  # 未添加则提示
async def _(
    matcher: AlconnaMatcher,
    add_leave: AddLeaveDepends,
    leave_image: UniMessage = ArgUniMessage("leave_image"),
):
    """处理当前命令或事件逻辑。"""
    print([i for i in leave_image])
    add_leave.add_message([i for i in leave_image])  # 再次保存内容
    if not add_leave.image_url:  # 如果二次没有提交则退出程序
        await matcher.finish(Emoji.error + "未能拿到您的证明图片，请重试！")

    if leave := await add_leave.send_message():
        if leave.is_valid:
            student_leave = await add_leave.save_student_leave(leave)
            await matcher.send(Emoji.success + leave.reply)
            await add_leave.notice_leave(student_leave)
        else:
            await matcher.finish(Emoji.error + leave.reply)
    else:
        await matcher.finish(Emoji.error + "请假提交失败！")


# --------------------------------- 请假列表 ---------------------------------


@query_leave_cmd.handle()
async def _(matcher: AlconnaMatcher, query_leave: QueryLeaveDepends):
    """处理当前命令或事件逻辑。"""
    leave_list = None
    if query_leave.is_classes_admin:
        leave_list = await query_leave.get_classes_leave()
    elif query_leave.is_student:
        leave_list = await query_leave.get_student_leave()

    if leave_list:
        for msg in query_leave.leave_to_messages(leave_list):
            await matcher.send(msg)
    else:
        await matcher.finish(Emoji.error + "您没有可查询请假信息")


# --------------------------------- 删除请假 ---------------------------------
@delete_leave_cmd.handle()
async def _(matcher: AlconnaMatcher, leave_id: list[str], query_leave: QueryLeaveDepends):
    """处理当前命令或事件逻辑。"""
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
