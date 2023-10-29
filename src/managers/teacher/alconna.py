from nonebot_plugin_alconna import At, Args, Field, Image, Alconna

add_teacher_alc = Alconna(
    "添加教师",
    Args["name", str, Field(completion=lambda: "请输入教师姓名")],
    Args["phone", int, Field(completion=lambda: "请输入教师手机号码")],
    Args["at", [str, At], Field(completion=lambda: "输入教师平台id或@教师")],
)

del_teacher_alc = Alconna("删除教师", Args["name", int, Field(completion=lambda: "输入教师id")])
