from utils import tip
from utils.config import alcoona_kwargs
from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

add_school = on_alconna(
    Alconna(
        "添加学校",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["address?", str | None, Field(default=None)],
    ),
    **alcoona_kwargs,
)
add_college = on_alconna(
    Alconna(
        "添加学院",
        Args["school_name", str, Field(completion=tip("请输入学校名称"))],
        Args["college_name", str, Field(completion=tip("请输入学院名称"))],
    ),
    **alcoona_kwargs,
)
