from nonebot import on_command, on_regex

add_notice = on_command("添加通知", aliases={"添加通知事件"}, priority=100, block=True)
show_notice = on_command("查询通知", aliases={"查看通知", "通知事件"}, priority=100, block=True)
del_notice = on_command("删除通知", aliases={"删除通知事件"}, priority=100, block=True)