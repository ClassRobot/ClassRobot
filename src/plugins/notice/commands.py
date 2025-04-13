from nonebot import on_command
from utils.config import priority, comp_config
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, on_alconna

notice_cmd = on_command(
    "创建通知",
    aliases={"定时", "转发"},
    priority=priority,
    block=True,
)
query_notice_cmd = on_alconna(
    Alconna("查询通知"),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
)
delete_notice_cmd = on_alconna(
    Alconna(
        "删除通知",
        Args["notice_id", MultiVar(str, "+"), Field(completion=lambda: "请输入通知ID")],
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


# __helpers__ = [
#     Helper(
#         command="创建通知",
#         aliases={"定时", "转发"},
#         description="向自己同学发起通知,或者定时消息,只需要在命令后面加上具体内容即可,用白话文的方式说明即可,AI会去解析你的意图",
#         params=[Param(name="具体内容", description="用白话文的方式描述自己需要通知的内容")],
#     ),
#     Helper(
#         command="查询通知",
#         description="查询自己发布的通知",
#     ),
#     Helper(
#         command="删除通知",
#         description="删除自己发布的通知",
#         params=[Param(name="通知ID", description="需要删除的通知ID")],
#     ),
# ]
