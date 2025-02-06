from utils.config import priority, comp_config
from utils import ValidateName, tip, alias_product
from src.plugins.helper.schemas import Param, Helper, ParamMode
from nonebot_plugin_alconna import (
    Args,
    File,
    Field,
    Image,
    Other,
    Alconna,
    MultiVar,
    on_alconna,
)

push_task_alias = alias_product(["上传", "提交"], ["作业", "任务"])
push_task_cmd = on_alconna(
    Alconna("提交任务", Args["task_arg", MultiVar(str | File | Image | Other, "*")]),
    aliases=push_task_alias,
    priority=priority,
    block=True,
    skip_for_unmatch=False,
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
    skip_for_unmatch=False,
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
    skip_for_unmatch=False,
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
    skip_for_unmatch=False,
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
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [
    Helper(
        command="提交任务",
        description="发布任务用于收集、清点、打包作业，支持上传文件、图片",
        aliases=push_task_alias,
        params=[Param(name="任务名称"), Param(name="文件或图片")],
        example="提交任务 任务1 [图片或文件]",
    ),
    Helper(
        command="创建任务",
        description="创建新的任务，指定任务名称",
        aliases=create_task_alias,
        params=[Param(name="任务名称")],
        example="创建任务 任务1",
    ),
    Helper(
        command="删除任务",
        description="删除指定名称的任务",
        aliases=delete_task_alias,
        params=[Param(name="任务名称")],
        example="删除任务 任务1",
    ),
    Helper(
        command="导出任务",
        description="机器人会将用户提交的任务文件打包发送给用户",
        aliases=export_task_alias,
        params=[Param(name="任务名称")],
        example="导出任务 任务1",
    ),
    Helper(
        command="查询任务",
        description="查询指定名称的任务，当不携带名称时显示所有任务",
        aliases=query_task_alias,
        params=[Param(name="任务名称", mode=ParamMode.OPTIONAL)],
        example="查询任务 任务1",
    ),
]

__all__ = [
    "push_task_cmd",
    "create_task_cmd",
    "delete_task_cmd",
    "export_task_cmd",
    "query_task_cmd",
]
