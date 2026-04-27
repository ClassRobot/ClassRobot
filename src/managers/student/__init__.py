from utils import Emoji
from utils.tools import StringCard
from utils.roles import StudentRoleLang
from utils.models.depends import StudentDepends
from nonebot_plugin_alconna import AlconnaMatcher
from utils.params.student import is_user_key, get_column_key, is_student_key, is_student_extra_key

from .commands import set_cmd, query_cmd


@query_cmd.handle()
async def _(matcher: AlconnaMatcher, student: StudentDepends):
    """查询学生信息。"""
    if student is None:
        await matcher.finish(Emoji.error + "您还未绑定学生信息！！")

    school_name = student.school.name if student.school else "未设置"
    major_name = student.classes.major_ref.name if student.classes.major_ref else (student.classes.major or "未设置")
    organizations = await student.get_organizations()
    organization_names = "、".join(organization.name for organization in organizations) if organizations else "暂无"
    student_role = StudentRoleLang[student.role] if student.role in StudentRoleLang._member_names_ else student.role

    card = (
        StringCard("学生信息")
        .text(f"学生ID: {student.id}")
        .text(f"姓名: {student.name}")
        .text(f"角色: {student_role}")
        .text(f"学校: {school_name}")
        .text(f"班级ID: {student.classes.id}")
        .text(f"班级名称: {student.classes.name}")
        .text(f"专业: {major_name}")
        .text(f"所属组织: {organization_names}")
        .text(f"创建日期: {student.created_at.strftime('%Y-%m-%d')}")
    )

    if student.extra:
        if student.extra.student_code:
            card.text(f"学号: {student.extra.student_code}")
        if student.extra.dormitory:
            card.text(f"寝室: {student.extra.dormitory}")
        if student.extra.family_contact:
            card.text(f"家庭联系方式: {student.extra.family_contact}")
        if student.extra.political_status:
            card.text(f"政治面貌: {student.extra.political_status}")
        if student.extra.family_address:
            card.text(f"家庭地址: {student.extra.family_address}")
        if student.extra.nation:
            card.text(f"民族: {student.extra.nation}")

    await matcher.finish(card.render())


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
