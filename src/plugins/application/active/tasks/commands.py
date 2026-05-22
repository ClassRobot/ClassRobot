from src.platform.config import priority, comp_config
from src.shared import ValidateName, tip, alias_product
from src.platform.commands import CommandBinding, CommandParam, on_agent_command
from src.platform.helper import HelperScope, UserRole
from nonebot_plugin_alconna import Args, File, Field, Image, Other, Alconna, MultiVar

push_task_alias = alias_product(["上传", "提交"], ["作业", "任务"])
push_task_cmd = on_agent_command(
    Alconna("提交任务", Args["task_arg", MultiVar(str | File | Image | Other, "*")]),
    aliases=push_task_alias,
    binding=CommandBinding(
        description="发布任务用于收集、清点、打包作业，支持上传文件和图片。",
        roles={UserRole.student},
        scopes={HelperScope.student},
        risk_level="medium",
        agent_callable=False,
        execution_mode="interactive",
        params=[
            CommandParam(
                name="任务名称/ID与附件",
                description="先写任务名称或ID，再附带文件、图片等提交内容。",
                multiple=True,
                source_name="task_arg",
            )
        ],
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
create_task_alias = alias_product(["创建", "发布"], ["作业", "任务"])
create_task_cmd = on_agent_command(
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
    binding=CommandBinding(
        description="创建新的任务，名称不能为纯数字。",
        roles={UserRole.student},
        scopes={HelperScope.student},
        risk_level="medium",
        agent_callable=False,
        param_labels={"task_name": "任务名称/ID"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
delete_task_alias = alias_product(["删除", "撤销"], ["作业", "任务"])
delete_task_cmd = on_agent_command(
    Alconna(
        "删除任务",
        Args["task_name?", str | None],
    ),
    aliases=delete_task_alias,
    binding=CommandBinding(
        description="通过任务名称或ID删除指定任务。",
        roles={UserRole.teacher, UserRole.student},
        scopes={HelperScope.student, HelperScope.teacher},
        risk_level="high",
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"task_name": "任务名称/ID"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
export_task_alias = alias_product(["导出", "下载"], ["作业", "任务"])
export_task_cmd = on_agent_command(
    Alconna(
        "导出任务",
        Args["task_name?", str | None],
    ),
    aliases=export_task_alias,
    binding=CommandBinding(
        description="把用户提交的任务文件打包导出并发送给用户。",
        roles={UserRole.teacher, UserRole.student},
        scopes={HelperScope.student, HelperScope.teacher},
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"task_name": "任务名称/ID"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)
query_task_alias = alias_product(["查询", "查看"], ["作业", "任务"])
query_task_cmd = on_agent_command(
    Alconna(
        "查询任务",
        Args["task_name?", str | None],
    ),
    aliases=query_task_alias,
    binding=CommandBinding(
        description="通过任务ID或名称查询；不携带名称时显示所有任务。",
        roles={UserRole.teacher, UserRole.student},
        scopes={HelperScope.student, HelperScope.teacher},
        param_labels={"task_name": "任务名称/ID"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helpers__ = [
    push_task_cmd.__helper__,
    create_task_cmd.__helper__,
    delete_task_cmd.__helper__,
    export_task_cmd.__helper__,
    query_task_cmd.__helper__,
]

__all__ = [
    "push_task_cmd",
    "create_task_cmd",
    "delete_task_cmd",
    "export_task_cmd",
    "query_task_cmd",
]
