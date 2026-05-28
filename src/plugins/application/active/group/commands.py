from typing import Optional

from src.shared import tip
from src.platform.config import alcoona_kwargs
from src.platform.helper import UserRole, HelperScope
from src.platform.commands.extensions import AdminExtension
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar
from src.platform.commands import CommandBinding, on_agent_command

add_school = on_agent_command(
    Alconna(
        "添加学校",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["address?", str | None, Field(default=None)],
    ),
    binding=CommandBinding(
        description="添加学校基础信息。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        param_labels={"school_name": "学校名称", "address": "地址"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

set_school = on_agent_command(
    Alconna(
        "修改学校",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args[
            "values", MultiVar(str, flag="+"), Field(completion=tip("修改方式如 名称=新校名 地址=新地址 描述=学校说明"))
        ],
    ),
    binding=CommandBinding(
        description="修改学校名称、地址、描述，采用 key=value 形式传参。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="medium",
        param_labels={"school_name": "学校名称", "values": "修改内容"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

delete_school = on_agent_command(
    Alconna("删除学校", Args["school_name", str, Field(completion=tip("请输入学校名称"))]),
    binding=CommandBinding(
        description="删除学校及其下属学院、专业、班级和组织，执行前会二次确认。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="high",
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"school_name": "学校名称"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

add_college = on_agent_command(
    Alconna(
        "添加学院",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
    ),
    binding=CommandBinding(
        description="为指定学校添加学院。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        param_labels={"school_name": "学校名称", "college_name": "学院名称"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

set_college = on_agent_command(
    Alconna(
        "修改学院",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["values", MultiVar(str, flag="+"), Field(completion=tip("修改方式如 名称=新学院 描述=学院说明"))],
    ),
    binding=CommandBinding(
        description="修改指定学校下学院的名称或描述，采用 key=value 形式传参。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="medium",
        param_labels={"school_name": "学校名称", "college_name": "学院名称", "values": "修改内容"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

delete_college = on_agent_command(
    Alconna(
        "删除学院",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
    ),
    binding=CommandBinding(
        description="删除指定学校下的学院及其专业、班级，执行前会二次确认。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="high",
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"school_name": "学校名称", "college_name": "学院名称"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

add_major = on_agent_command(
    Alconna(
        "添加专业",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["major_name", str, Field(completion=tip("请输入专业名称"))],
    ),
    binding=CommandBinding(
        description="为指定学校下的学院添加专业。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        param_labels={"school_name": "学校名称", "college_name": "学院名称", "major_name": "专业名称"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

set_major = on_agent_command(
    Alconna(
        "修改专业",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["major_name", str, Field(completion=tip("请输入专业名称"))],
        Args["values", MultiVar(str, flag="+"), Field(completion=tip("修改方式如 名称=新专业 描述=专业说明"))],
    ),
    binding=CommandBinding(
        description="修改指定专业的名称或描述，采用 key=value 形式传参。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="medium",
        param_labels={
            "school_name": "学校名称",
            "college_name": "学院名称",
            "major_name": "专业名称",
            "values": "修改内容",
        },
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

delete_major = on_agent_command(
    Alconna(
        "删除专业",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["major_name", str, Field(completion=tip("请输入专业名称"))],
    ),
    binding=CommandBinding(
        description="删除指定专业及其关联班级，执行前会二次确认。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="high",
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"school_name": "学校名称", "college_name": "学院名称", "major_name": "专业名称"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

add_organization = on_agent_command(
    Alconna(
        "添加组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
        Args["organization_type?", Optional[str], Field(default=None, completion=tip("可选：组织类型"))],
        Args["description?", Optional[str], Field(default=None, completion=tip("可选：组织说明"))],
    ),
    binding=CommandBinding(
        description="在指定学校下创建组织，可选指定组织类型和说明。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        param_labels={
            "school_name": "学校名称",
            "organization_name": "组织名称",
            "organization_type": "组织类型",
            "description": "组织说明",
        },
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

set_organization = on_agent_command(
    Alconna(
        "修改组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(completion=tip("修改方式如 名称=新组织 类型=interest 描述=组织说明")),
        ],
    ),
    binding=CommandBinding(
        description="修改组织名称、类型、说明，采用 key=value 形式传参。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="medium",
        param_labels={"school_name": "学校名称", "organization_name": "组织名称", "values": "修改内容"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

delete_organization = on_agent_command(
    Alconna(
        "删除组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
    ),
    binding=CommandBinding(
        description="删除指定学校下的组织，执行前会二次确认。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="high",
        agent_callable=False,
        execution_mode="interactive",
        param_labels={"school_name": "学校名称", "organization_name": "组织名称"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

query_structure = on_agent_command(
    Alconna(
        "查询组织架构",
        Args["school_name?", Optional[str], Field(default=None, completion=tip("可选：学校名称"))],
    ),
    aliases={"组织架构", "学校架构"},
    binding=CommandBinding(
        description="查看学校、学院、专业、班级与组织的整体结构；不携带学校名称时返回学校列表。",
        scopes={HelperScope.public},
        param_labels={"school_name": "学校名称"},
    ),
    **alcoona_kwargs,
)

query_organization = on_agent_command(
    Alconna(
        "查询组织",
        Args["school_name?", Optional[str], Field(default=None, completion=tip("可选：学校名称"))],
        Args["organization_name?", Optional[str], Field(default=None, completion=tip("可选：组织名称"))],
    ),
    aliases={"组织列表"},
    binding=CommandBinding(
        description="查看组织列表；可按学校过滤，也可继续查看某个组织的成员明细。",
        scopes={HelperScope.public},
        param_labels={"school_name": "学校名称", "organization_name": "组织名称"},
    ),
    **alcoona_kwargs,
)

join_organization = on_agent_command(
    Alconna(
        "加入组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
        Args["identity?", Optional[str], Field(default=None, completion=tip("可选：学生 或 教师"))],
        Args["position?", Optional[str], Field(default=None, completion=tip("可选：组织岗位"))],
    ),
    binding=CommandBinding(
        description="以学生或教师身份加入指定组织；双身份用户建议指定身份。",
        roles={UserRole.student, UserRole.teacher},
        scopes={HelperScope.student, HelperScope.teacher},
        risk_level="medium",
        agent_callable=False,
        param_labels={
            "school_name": "学校名称",
            "organization_name": "组织名称",
            "identity": "身份",
            "position": "岗位",
        },
    ),
    **alcoona_kwargs,
)

exit_organization = on_agent_command(
    Alconna(
        "退出组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
        Args["identity?", Optional[str], Field(default=None, completion=tip("可选：学生 或 教师"))],
    ),
    binding=CommandBinding(
        description="以学生或教师身份退出指定组织；双身份用户可指定身份。",
        roles={UserRole.student, UserRole.teacher},
        scopes={HelperScope.student, HelperScope.teacher},
        risk_level="medium",
        agent_callable=False,
        param_labels={"school_name": "学校名称", "organization_name": "组织名称", "identity": "身份"},
    ),
    **alcoona_kwargs,
)

set_college_manager = on_agent_command(
    Alconna(
        "设置学院负责人",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["teacher_id", int, Field(completion=tip("请输入教师ID"))],
    ),
    binding=CommandBinding(
        description="授予指定教师某学院负责人岗位。仅管理员可用。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="medium",
        agent_callable=False,
        param_labels={"school_name": "学校名称", "college_name": "学院名称", "teacher_id": "教师ID"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

unset_college_manager = on_agent_command(
    Alconna(
        "取消学院负责人",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["teacher_id", int, Field(completion=tip("请输入教师ID"))],
    ),
    binding=CommandBinding(
        description="撤销指定教师的学院负责人岗位。仅管理员可用。",
        roles={UserRole.admin},
        scopes={HelperScope.admin},
        risk_level="medium",
        agent_callable=False,
        param_labels={"school_name": "学校名称", "college_name": "学院名称", "teacher_id": "教师ID"},
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)
