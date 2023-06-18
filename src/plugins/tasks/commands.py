from nonebot import get_bot, on_command

add_task = on_command("添加任务", aliases={"新增任务", "增加任务"}, priority=100, block=True)
del_task = on_command("删除任务", aliases={"移除任务"}, priority=100, block=True)
# set_task = on_command("设置任务", aliases={"修改任务"}, priority=100, block=True)
push_task = on_command("提交任务", aliases={"上传任务"}, priority=100, block=True)
show_task = on_command("查询任务", aliases={"查看任务"}, priority=100, block=True)
export_task = on_command("导出任务", aliases={"提取任务"}, priority=100, block=True)
clear_task = on_command("清空任务", aliases={"删除所有任务"}, priority=100, block=True)


__helper__ = [
    {
        "cmd": "添加任务",
        "alias": ["新增任务", "增加任务"],
        "doc": "添加任务功能教师和学生都可以使用，但如果教师使用会多一个选择任务添加到指定班级的选项，"
        "添加完成任务后会告诉你任务ID，之后任务可以通过任务ID进行提交，也可以通过任务名。"
        "（目前任务功能只能对单个图片文件进行操作，还不支持其它文件）",
        "params": ["任务名称", "添加到指定班级（教师参数）"],
        "use": [["添加任务 青年大学习截图", "OK,任务ID：1"]],
        "tags": ["教师", "学生", "添加", "任务"],
    },
    {
        "cmd": "删除任务",
        "alias": ["移除任务"],
        "doc": "删除任务支持用ID或者任务名删除，推荐使用任务ID对任务进行删除，避免重名情况下误删！" "【同时支持多个任务删除】",
        "tags": ["删除", "任务", "教师", "学生"],
        "params": ["任务ID或任务名称"],
        "use": [["删除任务 1 2", "要删除的话请发送'确认'"], ["确认", "OK"]],
    },
    {
        "cmd": "提交任务",
        "alias": ["上传任务"],
        "doc": "只能由学生进行提交任务，并且只能提交到自己班级",
        "params": ["任务ID或任务名称", "文件（图片）"],
        "tags": ["提交", "任务", "学生"],
        "use": [["提交任务 1 [文件]", "OK"]],
    },
    {
        "cmd": "查询任务",
        "doc": "查询任务教师和学生都可以查询，教师只能查询自己创建班级所创建的任务，而学生只能查询自己班级的\n"
        "使用查询命令的时候，如果不带任务名称或任务ID则是查询所有任务的状态，当携带名称或ID时候将可以看到具体提交任务的名单",
        "params": ["任务ID或名称（可选）"],
        "tags": ["查询", "任务", "教师", "学生"],
        "use": [["查询任务", "[图片]"], ["查询任务1", ["已提交\n姓名 | 时间", "未提交\n姓名"]]],
    },
    {
        "cmd": "导出任务",
        "doc": "教师和学生都可以导出任务，并且也可以多个任务同时导出。",
        "params": ["任务id或名称"],
        "tags": ["导出", "任务", "学生", "教师"],
        "use": [["导出任务 1 2", ["[文件]", "[文件]"]]],
    },
]
