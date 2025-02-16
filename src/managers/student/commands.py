from utils import tip
from utils.config import priority, comp_config
from utils.params.student import get_columns_chinese
from src.plugins.helper.schemas import Param, Helper, ParamMode
from nonebot_plugin_alconna import Args, Field, Alconna, MultiVar, on_alconna

set_cmd = on_alconna(
    Alconna(
        "修改学生信息",
        Args[
            "values",
            MultiVar(str, flag="+"),
            Field(
                completion=tip(
                    f"修改方式如名字=张三 性别=男\n可以修改的内容:\n {', '.join(get_columns_chinese(['user_id']).values())}"
                )
            ),
        ],
    ),
    aliases={"修改学生", "设置学生信息"},
    block=True,
    priority=priority,
    skip_for_unmatch=False,
    comp_config=comp_config,
)


__helper__ = [
    Helper(
        command="修改学生信息",
        description=f"修改方式如名字=张三 性别=男\n可以修改的内容:\n {', '.join(get_columns_chinese(['user_id']).values())}",
        aliases={"修改学生", "设置学生信息"},
        params=[
            Param(
                name="values",
                mode=ParamMode.ONE_OR_MORE,
                description="修改方式如名字=张三 性别=男",
            ),
        ],
    )
]
