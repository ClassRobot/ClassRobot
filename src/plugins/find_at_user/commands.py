from nonebot import on_command

find_user = on_command("查询", aliases={"find", "查找"}, priority=100, block=True)
at_user = on_command("at", aliases={"@", "艾特"}, priority=100, block=True)
