from utils import Emoji
from nonebot_plugin_alconna import AlconnaMatcher
from utils.models.annotated import StudentDepends
from utils.params.student import (
    is_user_key,
    get_column_key,
    is_student_key,
    is_student_extra_key,
)

from .commands import set_cmd


@set_cmd.handle()
async def _(matcher: AlconnaMatcher, values: list[str], student: StudentDepends):
    if student is None:
        await matcher.finish(Emoji.error + "您还未绑定学生信息！！")

    options = {}
    for value in values:
        key, value = value.split("=")
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
