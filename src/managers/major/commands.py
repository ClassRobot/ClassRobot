from nonebot_plugin_alconna import Args, Field, Alconna, on_alconna

add_major_cmd = on_alconna(
    Alconna(
        "添加专业",
        Args["name", str, Field(completion=lambda: "请输入专业名称")],
        Args["college_name", str, Field(completion=lambda: "请输入院系名称")],
    )
)
