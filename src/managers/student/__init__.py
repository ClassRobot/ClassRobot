from utils import Emoji
from utils.models.depends import StudentDepends
from nonebot_plugin_alconna import AlconnaMatcher
from utils.params.student import is_user_key, get_column_key, is_student_key, is_student_extra_key

from .commands import query_cmd, set_cmd
from .presenters import render_student_card
# 导入统一命令 service，确保插件加载时完成 command_executor 注册。
from . import services as _


@query_cmd.handle()
async def _(matcher: AlconnaMatcher, student: StudentDepends):
    """查询学生信息。"""
    if student is None:
        await matcher.finish(Emoji.error + "您还未绑定学生信息！！")
    await matcher.finish(await render_student_card(student))


@set_cmd.handle()
async def _(matcher: AlconnaMatcher, values: list[str], student: StudentDepends):
    """处理当前命令或事件逻辑。"""
    if student is None:
        await matcher.finish(Emoji.error + "您还未绑定学生信息！！")

    options = {}
    for value in values:
        value_split = value.split("=")
        if len(value_split) != 2:
            await matcher.finish(Emoji.error + f"参数 {value} 格式错误！！\n应该采用 名字=张三 的形式")
        key, value = value_split
        if column := get_column_key(key):
            options[column] = value

    if not options:
        await matcher.finish(Emoji.error + "未找到有效参数！！")

    for key, value in options.items():
        if is_student_key(key):
            await student.update(**{key: value})
        elif is_student_extra_key(key):
            if not student.extra:
                await student.create_extra()
            await student.extra.update(**{key: value})  # type: ignore
        elif is_user_key(key):
            await student.user.update(**{key: value})

    await matcher.finish(Emoji.success + "设置成功！！")
