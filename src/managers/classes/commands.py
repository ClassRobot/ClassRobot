from typing import Optional

from utils import ValidateName, FileOrOtherFile, tip
from utils.helper import Param, Helper, UserRole, ParamMode
from utils.config import priority, comp_config, alcoona_kwargs
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

import_classes_cmd = on_alconna(
    Alconna(
        "导入班级",
        Args["import_file", FileOrOtherFile, Field(completion=tip("请发送导入班级表格"))],
    ),
    **alcoona_kwargs,
)

create_classes_cmd = on_alconna(
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
    comp_config=comp_config,
    block=True,
)

delete_classes_cmd = on_alconna(
    Alconna("删除班级", Args["classes_id?", Optional[int]]),
    skip_for_unmatch=False,
    comp_config=comp_config,
    priority=priority,
    block=True,
)

query_classes_cmd = on_alconna(
    Alconna("查询班级", Args["classes_id?", Optional[int]]),
    aliases={"班级列表", "我的班级"},
    priority=priority,
    block=True,
)

query_join_request_cmd = on_alconna(
    Alconna("查询入班申请", Args["classes_id?", Optional[int]]),
    aliases={"入班申请列表"},
    priority=priority,
    block=True,
)

review_join_request_cmd = on_alconna(
    Alconna(
        "处理入班申请",
        Args["request_id", int, Field(completion=tip("请输入申请ID"))],
        Args["action", str, Field(completion=tip("请输入 通过 或 拒绝"))],
    ),
    aliases={"审核入班申请"},
    priority=priority,
    block=True,
    skip_for_unmatch=False,
    comp_config=comp_config,
)

join_classes_cmd = on_alconna(
    Alconna("加入班级", Args["classes_id?", Optional[int]], Args["describe?", Optional[str]]),
    skip_for_unmatch=False,
    comp_config=comp_config,
    priority=priority,
    block=True,
)

# 修改加入班级方式
set_join_classes_cmd = on_alconna(
    Alconna(
        "修改班级加入方式",
        Args["classes_id?", Optional[str]],
        Args["join_method?", Optional[str]],
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
    priority=priority,
    block=True,
)

# 退出班级
exit_classes_cmd = on_alconna(
    Alconna("退出班级"),
    skip_for_unmatch=False,
    comp_config=comp_config,
    priority=priority,
    block=True,
)

__helpers__ = [
    Helper(
        command="添加班级",
        description="创建一个自己的班级，创建后默认会成为该班级教师；也可以把已管理的班级按名称绑定到当前群，并可选补充学校/学院/专业信息。",
        aliases={"创建班级", "绑定班级"},
        params=[
            Param(name="班级名称"),
            Param(name="学校名称", mode=ParamMode.OPTIONAL),
            Param(name="学院名称", mode=ParamMode.OPTIONAL),
            Param(name="专业名称", mode=ParamMode.OPTIONAL),
        ],
        roles={UserRole.user},
        ai_description="学生不可用；如果班级已存在且当前用户是该班级教师，则会把当前群绑定到已有班级。",
    ),
    Helper(
        command="查询班级",
        description="查询自己管理的班级；可选携带班级ID查看单个班级的详细信息。",
        aliases={"班级列表", "我的班级"},
        params=[Param(name="班级ID", mode=ParamMode.OPTIONAL)],
        roles={UserRole.teacher},
    ),
    Helper(
        command="查询入班申请",
        description="查询自己管理班级的待处理入班申请；群聊中可直接查看当前班级群的申请，私聊可选携带班级ID。",
        aliases={"入班申请列表"},
        params=[Param(name="班级ID", mode=ParamMode.OPTIONAL)],
        roles={UserRole.teacher},
    ),
    Helper(
        command="处理入班申请",
        description="处理指定入班申请，可选择通过或拒绝。",
        aliases={"审核入班申请"},
        params=[Param(name="申请ID"), Param(name="处理结果")],
        roles={UserRole.teacher},
    ),
    Helper(
        command="加入班级",
        description="可通过班级ID加入指定班级；如果在班级群中执行且不携带班级ID，则会自动识别当前群对应的班级。",
        params=[Param(name="班级ID", mode=ParamMode.OPTIONAL)],
        roles={UserRole.user},
    ),
    Helper(
        command="导入班级",
        description="通过 Excel 批量导入班级和学生数据，至少需要包含学校、学院、班级、姓名、学号列。",
        params=[Param(name="导入文件")],
        roles={UserRole.teacher},
    ),
    Helper(
        command="退出班级",
        description="退出当前班级",
        roles={UserRole.student},
    ),
    Helper(
        command="删除班级",
        description="删除自己的班级",
        aliases={"解散班级"},
        params=[Param(name="班级ID", mode=ParamMode.OPTIONAL)],
        roles={UserRole.teacher},
    ),
    Helper(
        command="修改班级加入方式",
        description="修改班级的加入方式，可设置为直接通过、申请加入或邀请加入；私聊建议携带班级ID，群聊中可直接作用于当前班级群。",
        params=[
            Param(name="班级ID", mode=ParamMode.OPTIONAL),
            Param(name="加入方式", mode=ParamMode.OPTIONAL),
        ],
        roles={UserRole.teacher},
    ),
]
