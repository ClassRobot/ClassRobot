from typing import Optional

from utils import ValidateName, FileOrOtherFile, tip
from utils.commands import CommandBinding, on_agent_command
from utils.helper import HelperScope, UserRole
from utils.config import priority, comp_config, alcoona_kwargs
from nonebot_plugin_alconna import Args, Field, Alconna, CommandMeta

import_classes_cmd = on_agent_command(
    Alconna(
        "导入班级",
        Args["import_file", FileOrOtherFile, Field(completion=tip("请发送导入班级表格"))],
    ),
    binding=CommandBinding(
        description="通过 Excel 批量导入班级和学生数据，至少需要包含学校、学院、班级、姓名、学号列。",
        roles={UserRole.user, UserRole.teacher},
        exclude_roles={UserRole.student},
        scopes={HelperScope.teacher},
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"import_file": "导入文件"},
    ),
    **alcoona_kwargs,
)

create_classes_cmd = on_agent_command(
    Alconna(
        "添加班级",
        Args[
            "class_name",
            ValidateName,
            Field(
                completion=tip("请输入班级名称"),
                unmatch_tips=tip("名称不能为纯数字或携带特殊字符"),
            ),
        ],
        Args["school_name?", Optional[str], Field(default=None, completion=tip("可选：学校名称"))],
        Args["college_name?", Optional[str], Field(default=None, completion=tip("可选：学院名称"))],
        Args["major_name?", Optional[str], Field(default=None, completion=tip("可选：专业名称"))],
    ),
    skip_for_unmatch=False,
    priority=priority,
    aliases={"创建班级", "绑定班级"},
    binding=CommandBinding(
        description="创建一个自己的班级，创建后默认会成为该班级教师；也可以把已管理的班级按名称绑定到当前群，并可选补充学校、学院、专业信息。",
        ai_description="学生不可用；如果班级已存在且当前用户是该班级教师，则会把当前群绑定到已有班级。",
        roles={UserRole.user, UserRole.teacher},
        exclude_roles={UserRole.student},
        scopes={HelperScope.teacher},
        param_labels={
            "class_name": "班级名称",
            "school_name": "学校名称",
            "college_name": "学院名称",
            "major_name": "专业名称",
        },
    ),
    comp_config=comp_config,
    block=True,
)

delete_classes_cmd = on_agent_command(
    Alconna("删除班级", Args["classes_id?", Optional[int]]),
    aliases={"解散班级"},
    binding=CommandBinding(
        description="删除自己管理的班级；私聊中可指定班级ID，群聊中可直接作用于当前班级群。",
        roles={UserRole.teacher},
        scopes={HelperScope.teacher},
        risk_level="high",
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"classes_id": "班级ID"},
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
    priority=priority,
    block=True,
)

query_classes_cmd = on_agent_command(
    Alconna(
        "查询班级",
        Args["classes_id?", Optional[int]],
        meta=CommandMeta(description="查询自己管理的班级；可选携带班级 ID 查看单个班级详情。"),
    ),
    aliases={"班级列表", "我的班级"},
    binding=CommandBinding(
        roles={UserRole.teacher},
        scopes={HelperScope.teacher},
        tags={"classes", "query"},
        execution_mode="service",
        param_labels={"classes_id": "班级ID"},
    ),
    priority=priority,
    block=True,
)

query_join_request_cmd = on_agent_command(
    Alconna("查询入班申请", Args["classes_id?", Optional[int]]),
    aliases={"入班申请列表"},
    binding=CommandBinding(
        description="查询自己管理班级的待处理入班申请；群聊中可直接查看当前班级群的申请，私聊可选携带班级ID。",
        roles={UserRole.teacher},
        scopes={HelperScope.teacher},
        param_labels={"classes_id": "班级ID"},
    ),
    priority=priority,
    block=True,
)

review_join_request_cmd = on_agent_command(
    Alconna(
        "处理入班申请",
        Args["request_id", int, Field(completion=tip("请输入申请ID"))],
        Args["action", str, Field(completion=tip("请输入 通过 或 拒绝"))],
    ),
    aliases={"审核入班申请"},
    binding=CommandBinding(
        description="处理指定入班申请，可选择通过或拒绝。",
        roles={UserRole.teacher},
        scopes={HelperScope.teacher},
        risk_level="medium",
        agent_callable=False,
        param_labels={"request_id": "申请ID", "action": "处理结果"},
    ),
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

join_classes_cmd = on_agent_command(
    Alconna("加入班级", Args["classes_id?", Optional[int]], Args["describe?", Optional[str]]),
    binding=CommandBinding(
        description="可通过班级ID加入指定班级；如果在班级群中执行且不携带班级ID，则会自动识别当前群对应的班级。",
        roles={UserRole.user},
        exclude_roles={UserRole.student, UserRole.teacher},
        scopes={HelperScope.student},
        risk_level="medium",
        agent_callable=False,
        param_labels={"classes_id": "班级ID", "describe": "申请说明"},
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
    priority=priority,
    block=True,
)

set_join_classes_cmd = on_agent_command(
    Alconna(
        "修改班级加入方式",
        Args["classes_id?", Optional[str]],
        Args["join_method?", Optional[str]],
    ),
    binding=CommandBinding(
        description="修改班级的加入方式，可设置为直接通过、申请加入或邀请加入；私聊建议携带班级ID，群聊中可直接作用于当前班级群。",
        roles={UserRole.teacher},
        scopes={HelperScope.teacher},
        risk_level="medium",
        agent_callable=False,
        param_labels={"classes_id": "班级ID", "join_method": "加入方式"},
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
    priority=priority,
    block=True,
)

exit_classes_cmd = on_agent_command(
    Alconna("退出班级"),
    binding=CommandBinding(
        description="退出当前班级。",
        roles={UserRole.student},
        scopes={HelperScope.student},
        risk_level="medium",
        agent_callable=False,
        execution_mode="interactive",
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
    priority=priority,
    block=True,
)

__helpers__ = [
    import_classes_cmd.__helper__,
    create_classes_cmd.__helper__,
    delete_classes_cmd.__helper__,
    query_classes_cmd.__helper__,
    query_join_request_cmd.__helper__,
    review_join_request_cmd.__helper__,
    join_classes_cmd.__helper__,
    set_join_classes_cmd.__helper__,
    exit_classes_cmd.__helper__,
]
