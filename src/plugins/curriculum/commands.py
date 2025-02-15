from utils import tip
from utils.config import comp_config
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, on_alconna

add_curriculum = on_alconna(
    Alconna(
        "添加课表",
        Args[
            "curriculum",
            MultiVar(str, flag="+"),
            Field(unmatch_tips=tip("课表内容不能为空")),
        ],
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
)
add_classes_curriculum = on_alconna(
    Alconna(
        "添加班级课表",
        Args[
            "curriculum",
            MultiVar(str, flag="+"),
            Field(unmatch_tips=tip("课表内容不能为空")),
        ],
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
)
del_curriculum = on_alconna(
    Alconna(
        "删除课表",
        Args["curriculum_id", MultiVar(int, flag="+")],
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
)
query_curriculum = on_alconna(
    Alconna(
        "查询课表",
        Args["curriculum_id", MultiVar(int, flag="+")],
    ),
    skip_for_unmatch=False,
    comp_config=comp_config,
)
