from utils.typings import UserType
from utils.config import comp_config
from src.others.helper import add_help
from src.others.helper.typings import Helper, ExampleMessage
from nonebot_plugin_alconna import At, Args, Field, Alconna, on_alconna
from utils.params.args import NameOrId, NameNotNumeric, name_not_numeric_args
from utils.auth.extension import UserExtension, TeacherExtension, ClassTableExtension

add_class_table_cmd = on_alconna(
    Alconna(
        "添加班级",
        NameNotNumeric.class_name(),
        NameOrId.major_name(),
    ),
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

join_class_table_cmd = on_alconna(
    Alconna(
        "加入班级",
        NameNotNumeric.student_name(),
        NameOrId.class_name(),
    ),
    aliases={"成为班级学生"},
    block=True,
    comp_config=comp_config,
    extensions=[UserExtension],
)

del_class_table_cmd = on_alconna(
    Alconna(
        "删除班级",
        Args["class_name_or_id", str | int, Field(completion=lambda: "请输入班级名称或班级id")],
    ),
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

bind_class_table_cmd = on_alconna(
    Alconna(
        "绑定班级群",
        Args["class_name_or_id", str, Field(completion=lambda: "请输入班级名称或班级id")],
    ),
    aliases={"绑定班级"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

unbind_class_table_cmd = on_alconna(
    Alconna(
        "解绑班级群",
    ),
    block=True,
    comp_config=comp_config,
    extensions=[ClassTableExtension, TeacherExtension],
)

show_class_table_cmd = on_alconna(
    "查询班级",
    aliases={"查看班级", "班级列表", "我的班级"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

transfer_class_table_cmd = on_alconna(
    Alconna(
        "转让班级",
        Args["class_name_or_id", int | str, Field(completion=lambda: "请输入班级名称或班级id")],
        Args["user_id_or_at", int | At, Field(completion=lambda: "请输入教师用户id或at教师")],
    ),
    aliases={"移交班级"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

view_class_table_in_group_cmd = on_alconna(
    Alconna(
        "查看本群班级",
    ),
    aliases={"查看此群班级", "查看本群"},
    block=True,
    comp_config=comp_config,
    extensions=[UserExtension],
)

add_help(
    Helper(
        command="添加班级",
        description="教师身份来添加班级，默认会将命令执行的群作为班级群",
        usage="添加班级 [班级名称] [专业名称]",
        example=[
            ExampleMessage(user_type=UserType.TEACHER, message="添加班级 人工智能001 人工智能"),
            ExampleMessage(user_type="bot", message="[人工智能001]班添加成功"),
        ],
        category={"添加", "班级"},
    ),
    Helper(
        command="加入班级",
        description="普通用户加入班级成为学生",
        usage="加入班级 [您的姓名] [班级名称或班级id]",
        example=[
            ExampleMessage(user_type=UserType.USER, message="加入班级 张三 人工智能001"),
            ExampleMessage(user_type="bot", message="[张三]成功加入[人工智能]"),
        ],
        aliases={"成为班级学生"},
        category={"加入", "班级"},
    ),
    Helper(
        command="删除班级",
        description="删除教师自己创建的班级",
        usage="删除班级 [班级名称或班级id]",
        example=[
            ExampleMessage(user_type=UserType.TEACHER, message="删除班级 人工智能"),
            ExampleMessage(user_type="bot", message="[人工智能] 删除成功"),
        ],
        category={"删除", "班级"},
    ),
    Helper(
        command="绑定班级群",
        description="将当前的群与班级进行绑定",
        usage="绑定班级 [班级名称或班级id]",
        example=[
            ExampleMessage(user_type=UserType.TEACHER, message="绑定班级 人工智能"),
            ExampleMessage(user_type="bot", message="[人工智能] 绑定成功"),
        ],
        aliases={"绑定班级"},
        category={"绑定", "班级"},
    ),
    Helper(
        command="解绑班级群",
        description="解绑当前群与班级的绑定",
        usage="解绑班级群",
        example=[
            ExampleMessage(user_type=UserType.TEACHER, message="解绑班级群"),
            ExampleMessage(user_type="bot", message="解绑成功"),
        ],
        category={"解绑", "班级"},
    ),
    Helper(
        command="转让班级",
        description="转让班级给其他教师",
        usage="转让班级 [班级名称或班级id] [教师用户id或at教师]",
        example=[
            ExampleMessage(user_type=UserType.TEACHER, message="转让班级 人工智能 123456"),
            ExampleMessage(user_type="bot", message="[人工智能] 转让成功"),
        ],
        aliases={"移交班级"},
        category={"转让", "班级"},
    ),
    Helper(
        command="查询班级",
        description="用于查询教师自己添加的班级",
        usage="查询班级",
        example=[
            ExampleMessage(user_type=UserType.USER, message="查询班级"),
            ExampleMessage(user_type="bot", message="您所创建的班级如下:\n1. 人工智能"),
        ],
        aliases={"查看班级", "班级列表", "我的班级"},
        category={"查询", "班级"},
    ),
)
