from typing import Optional

from utils import tip
from utils.config import alcoona_kwargs
from utils.extensions import AdminExtension
from utils.helper import Param, Helper, UserRole, ParamMode
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, on_alconna

add_school = on_alconna(
    Alconna(
        "添加学校",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["address?", str | None, Field(default=None)],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

set_school = on_alconna(
    Alconna(
        "修改学校",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["values", MultiVar(str, flag="+"), Field(completion=tip("修改方式如 名称=新校名 地址=新地址 描述=学校说明"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

delete_school = on_alconna(
    Alconna("删除学校", Args["school_name", str, Field(completion=tip("请输入学校名称"))]),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

add_college = on_alconna(
    Alconna(
        "添加学院",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

set_college = on_alconna(
    Alconna(
        "修改学院",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["values", MultiVar(str, flag="+"), Field(completion=tip("修改方式如 名称=新学院 描述=学院说明"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

delete_college = on_alconna(
    Alconna(
        "删除学院",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

add_major = on_alconna(
    Alconna(
        "添加专业",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["major_name", str, Field(completion=tip("请输入专业名称"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

set_major = on_alconna(
    Alconna(
        "修改专业",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["major_name", str, Field(completion=tip("请输入专业名称"))],
        Args["values", MultiVar(str, flag="+"), Field(completion=tip("修改方式如 名称=新专业 描述=专业说明"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

delete_major = on_alconna(
    Alconna(
        "删除专业",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
        Args["major_name", str, Field(completion=tip("请输入专业名称"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

add_organization = on_alconna(
    Alconna(
        "添加组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
        Args["organization_type?", Optional[str], Field(default=None, completion=tip("可选：组织类型"))],
        Args["description?", Optional[str], Field(default=None, completion=tip("可选：组织说明"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

set_organization = on_alconna(
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
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

delete_organization = on_alconna(
    Alconna(
        "删除组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
    ),
    **alcoona_kwargs,
    extensions=[AdminExtension],
)

query_structure = on_alconna(
    Alconna(
        "查询组织架构",
        Args["school_name?", Optional[str], Field(default=None, completion=tip("可选：学校名称"))],
    ),
    aliases={"组织架构", "学校架构"},
    **alcoona_kwargs,
)

query_organization = on_alconna(
    Alconna(
        "查询组织",
        Args["school_name?", Optional[str], Field(default=None, completion=tip("可选：学校名称"))],
        Args["organization_name?", Optional[str], Field(default=None, completion=tip("可选：组织名称"))],
    ),
    aliases={"组织列表"},
    **alcoona_kwargs,
)

join_organization = on_alconna(
    Alconna(
        "加入组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
        Args["identity?", Optional[str], Field(default=None, completion=tip("可选：学生 或 教师"))],
        Args["position?", Optional[str], Field(default=None, completion=tip("可选：组织岗位"))],
    ),
    **alcoona_kwargs,
)

exit_organization = on_alconna(
    Alconna(
        "退出组织",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["organization_name", str, Field(completion=tip("请输入组织名称"))],
        Args["identity?", Optional[str], Field(default=None, completion=tip("可选：学生 或 教师"))],
    ),
    **alcoona_kwargs,
)


__helpers__ = [
    Helper(
        command="添加学校",
        description="添加学校基础信息。",
        params=[Param(name="学校名称"), Param(name="地址", mode=ParamMode.OPTIONAL)],
        roles={UserRole.admin},
    ),
    Helper(
        command="修改学校",
        description="修改学校名称、地址、描述，采用 key=value 形式传参。",
        params=[Param(name="学校名称"), Param(name="values", mode=ParamMode.ONE_OR_MORE)],
        roles={UserRole.admin},
    ),
    Helper(
        command="删除学校",
        description="删除学校及其下属学院、专业、班级和组织，执行前会二次确认。",
        params=[Param(name="学校名称")],
        roles={UserRole.admin},
    ),
    Helper(
        command="添加学院",
        description="为指定学校添加学院。",
        params=[Param(name="学校名称"), Param(name="学院名称")],
        roles={UserRole.admin},
    ),
    Helper(
        command="修改学院",
        description="修改指定学校下学院的名称或描述，采用 key=value 形式传参。",
        params=[Param(name="学校名称"), Param(name="学院名称"), Param(name="values", mode=ParamMode.ONE_OR_MORE)],
        roles={UserRole.admin},
    ),
    Helper(
        command="删除学院",
        description="删除指定学校下的学院及其专业、班级，执行前会二次确认。",
        params=[Param(name="学校名称"), Param(name="学院名称")],
        roles={UserRole.admin},
    ),
    Helper(
        command="添加专业",
        description="为指定学校下的学院添加专业。",
        params=[Param(name="学校名称"), Param(name="学院名称"), Param(name="专业名称")],
        roles={UserRole.admin},
    ),
    Helper(
        command="修改专业",
        description="修改指定专业的名称或描述，采用 key=value 形式传参。",
        params=[
            Param(name="学校名称"),
            Param(name="学院名称"),
            Param(name="专业名称"),
            Param(name="values", mode=ParamMode.ONE_OR_MORE),
        ],
        roles={UserRole.admin},
    ),
    Helper(
        command="删除专业",
        description="删除指定专业及其关联班级，执行前会二次确认。",
        params=[Param(name="学校名称"), Param(name="学院名称"), Param(name="专业名称")],
        roles={UserRole.admin},
    ),
    Helper(
        command="添加组织",
        description="在指定学校下创建组织，可选指定组织类型和说明。",
        params=[
            Param(name="学校名称"),
            Param(name="组织名称"),
            Param(name="组织类型", mode=ParamMode.OPTIONAL),
            Param(name="组织说明", mode=ParamMode.OPTIONAL),
        ],
        roles={UserRole.admin},
    ),
    Helper(
        command="修改组织",
        description="修改组织名称、类型、说明，采用 key=value 形式传参。",
        params=[Param(name="学校名称"), Param(name="组织名称"), Param(name="values", mode=ParamMode.ONE_OR_MORE)],
        roles={UserRole.admin},
    ),
    Helper(
        command="删除组织",
        description="删除指定学校下的组织，执行前会二次确认。",
        params=[Param(name="学校名称"), Param(name="组织名称")],
        roles={UserRole.admin},
    ),
    Helper(
        command="查询组织架构",
        description="查看学校、学院、专业、班级与组织的整体结构；不携带学校名称时返回学校列表。",
        aliases={"组织架构", "学校架构"},
        params=[Param(name="学校名称", mode=ParamMode.OPTIONAL)],
    ),
    Helper(
        command="查询组织",
        description="查看组织列表；可按学校过滤，也可继续查看某个组织的成员明细。",
        aliases={"组织列表"},
        params=[
            Param(name="学校名称", mode=ParamMode.OPTIONAL),
            Param(name="组织名称", mode=ParamMode.OPTIONAL),
        ],
    ),
    Helper(
        command="加入组织",
        description="当前用户以学生或教师身份加入指定组织；当同时具备学生和教师身份时建议显式指定身份。",
        params=[
            Param(name="学校名称"),
            Param(name="组织名称"),
            Param(name="身份", mode=ParamMode.OPTIONAL),
            Param(name="岗位", mode=ParamMode.OPTIONAL),
        ],
        roles={UserRole.user},
        ai_description="执行时必须已经绑定学生或教师身份；普通用户不能直接成为组织成员。",
    ),
    Helper(
        command="退出组织",
        description="当前用户以学生或教师身份退出指定组织。",
        params=[
            Param(name="学校名称"),
            Param(name="组织名称"),
            Param(name="身份", mode=ParamMode.OPTIONAL),
        ],
        roles={UserRole.user},
        ai_description="执行时必须已经绑定学生或教师身份；若同时具备学生和教师身份，建议显式指定身份。",
    ),
]
