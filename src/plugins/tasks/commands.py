from utils.config import priority, comp_config
from utils import ValidateName, tip, alias_product
from nonebot_plugin_alconna import Args, File, Field, Image, Other, Alconna, on_alconna

push_task_alias = alias_product(["上传", "提交"], ["作业", "任务"])
push_task_cmd = on_alconna(
    Alconna(
        "提交任务",
        Args["file", Image | File | Other, Field(completion=lambda: "发送文件给我吧")],
    ),
    aliases=push_task_alias,
    priority=priority,
    block=True,
    comp_config=comp_config,
)
create_task_alias = alias_product(["创建", "发布"], ["作业", "任务"])
create_task_cmd = on_alconna(
    Alconna(
        "创建任务",
        Args[
            "task_name",
            ValidateName,
            Field(
                completion=lambda: "请输入任务名称",
                unmatch_tips=tip("名称不能为纯数字"),
            ),
        ],
    ),
    aliases=create_task_alias,
    priority=priority,
    block=True,
    comp_config=comp_config,
)
delete_task_alias = alias_product(["删除", "撤销"], ["作业", "任务"])
delete_task_cmd = on_alconna(
    Alconna(
        "删除任务",
        Args["task_name?", str | None],
    ),
    aliases=delete_task_alias,
    priority=priority,
    block=True,
    comp_config=comp_config,
)
export_task_alias = alias_product(["导出", "下载"], ["作业", "任务"])
export_task_cmd = on_alconna(
    Alconna(
        "导出任务",
        Args["task_name?", str | None],
    ),
    aliases=export_task_alias,
    priority=priority,
    block=True,
    comp_config=comp_config,
)
query_task_alias = alias_product(["查询", "查看"], ["作业", "任务"])
query_task_cmd = on_alconna(
    Alconna(
        "查询任务",
        Args["task_name?", str | None],
    ),
    aliases=query_task_alias,
    priority=priority,
    block=True,
    comp_config=comp_config,
)
