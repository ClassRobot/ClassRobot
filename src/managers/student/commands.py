from utils.config import comp_config
from utils.typings import UserType, class_cadres
from src.others.helper import Helper, ExampleMessage, add_help
from utils.auth.extension import StudentExtension, TeacherExtension
from nonebot_plugin_alconna import At, Args, Field, Alconna, MultiVar, on_alconna

class_cadre_select = "选择职位:\n" + "\n".join(f"● {i}" for i in class_cadres)

add_student_cmd = on_alconna(
    Alconna(
        "添加学生",
        Args["validate_name", str, Field(completion=lambda: "请输入学生姓名")],
        Args[
            "class_name_or_id",
            str,
            Field(completion=lambda: "请输入添加到的班级名称或班级id"),
        ],
        Args["user_id", int, Field(completion=lambda: "请输入这位学生的用户id")],
    ),
    aliases={"增加学生"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

search_student_cmd = on_alconna(
    Alconna(
        "查询学生",
        Args[
            "user_keys",
            MultiVar(int, flag="+"),
            Field(completion=lambda: "请输入一位或多为学生的姓名或学生id"),
        ],
    ),
    aliases={"搜索学生", "查看学生"},
    block=True,
    comp_config=comp_config,
    extensions=[StudentExtension],
)

set_class_cadre_cmd = on_alconna(
    Alconna(
        "设置班干",
        Args[
            "user_id_or_at",
            int | At,
            Field(completion=lambda: "请输入学生的用户id或at"),
        ],
        Args["class_cadre", str, Field(completion=lambda: class_cadre_select)],
    ),
    aliases={"设置班干部", "设置班委", "添加班委", "修改班委"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)

del_student_cmd = on_alconna(
    Alconna(
        "删除学生",
        Args[
            "user_ids",
            MultiVar(str, flag="+"),
            Field(completion=lambda: "请输入一位或多为学生的学生id（学生id非用户id）"),
        ],
    ),
    aliases={"移除学生"},
    block=True,
    comp_config=comp_config,
    extensions=[TeacherExtension],
)


add_help(
    Helper(
        command="添加学生",
        description="教师身份来添加学生",
        usage="添加学生 [学生姓名] [班级名称或班级id] [用户id]",
        example=[
            ExampleMessage(
                user_type=UserType.TEACHER, message="添加学生 张三 人工智能 123456"
            ),
            ExampleMessage(user_type="bot", message="张三 添加成功"),
        ],
        aliases={"增加学生"},
        category={"添加", "学生"},
    ),
    Helper(
        command="删除学生",
        description="教师身份来删除学生",
        usage="删除学生 [学生id1] [学生id2] ...",
        example=[
            ExampleMessage(user_type=UserType.TEACHER, message="删除学生 123456"),
            ExampleMessage(user_type="bot", message="123456 删除成功"),
        ],
        aliases={"移除学生"},
        category={"删除", "学生"},
    ),
)
