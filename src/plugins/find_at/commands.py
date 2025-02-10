from utils.config import priority
from src.plugins.helper.schemas import Param, Helper, ParamMode
from nonebot_plugin_alconna import Args, Alconna, MultiVar, on_alconna

from .util import columns_chinese

find_cmd = on_alconna(
    Alconna("find", Args["items", MultiVar(str, "+")]),
    aliases={"查找", "查询"},
    priority=priority + 10,
    block=True,
)

at_cmd = on_alconna(
    Alconna("at", Args["items", MultiVar(str, "+")]),
    aliases={"艾特"},
    priority=priority,
    block=True,
)

__helpers__ = [
    Helper(
        command="find",
        aliases={"查找", "查询"},
        description=(
            "查找自己班级的学生或同学,可以通过多个关键信息进行搜索."
            "例如:`李四 张三`就可以搜索到李四和张三两个同学的信息."
            "或者使用`.`进行子条件搜索."
            "例如:`1班.张三`表示在1班中搜索名字为张三的学生,`1-123.张三`就可以搜索`1-123`寝室的张三."
            "支持如下搜索条件：" + "\\".join(columns_chinese)
        ),
        params=[
            Param(
                name="搜索条件",
                mode=ParamMode.ONE_OR_MORE,
            )
        ],
    ),
    Helper(
        command="at",
        aliases={"艾特"},
        description="at命令可以通过关键信息搜索到对应的用户并at他们,搜索条件与`查找`功能一样.",
        params=[
            Param(
                name="搜索条件",
                mode=ParamMode.ONE_OR_MORE,
            )
        ],
    ),
]
