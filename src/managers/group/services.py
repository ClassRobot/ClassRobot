from __future__ import annotations

from nonebot.adapters import Event
from nonebot_plugin_alconna import AlconnaMatcher
from nonebot_plugin_waiter import waiter

from utils import Emoji
from utils.models import Classes, College, Major, Organization, School
from utils.models.depends import UserOrCreatedDepends

from .constants import IDENTITY_MAPPING, ORGANIZATION_TYPE_LABELS


def get_organization_type_label(organization_type: str) -> str:
    """返回组织类型的展示文案。

    Args:
        organization_type: 数据库中保存的组织类型枚举值。

    Returns:
        str: 用户可读的组织类型名称；未知类型会原样返回。
    """

    return ORGANIZATION_TYPE_LABELS.get(organization_type, organization_type)


def parse_update_values(values: list[str], mapping: dict[str, list[str]]) -> dict[str, str]:
    """解析 ``key=value`` 形式的更新字段。

    Args:
        values: 用户输入的原始更新参数列表。
        mapping: 可修改字段到中文别名的映射表。

    Returns:
        dict[str, str]: 解析后可传给模型更新方法的字段字典。

    Raises:
        ValueError: 当参数不是 ``key=value`` 格式时抛出。
    """

    options = {}
    for item in values:
        key_value = item.split("=", 1)
        if len(key_value) != 2:
            raise ValueError(f"参数 {item} 格式错误，应采用 名称=新值 的形式。")
        raw_key, raw_value = key_value
        raw_key = raw_key.strip()
        raw_value = raw_value.strip()
        if not raw_value:
            continue
        for field, aliases in mapping.items():
            if raw_key in aliases:
                options[field] = raw_value
                break
    return options


async def confirm_action(matcher: AlconnaMatcher, prompt: str) -> bool:
    """等待用户确认危险操作。

    Args:
        matcher: 当前命令 matcher，用于发送确认提示。
        prompt: 需要发送给用户的确认文案。

    Returns:
        bool: 用户在 60 秒内回复 ``yes`` 时返回 ``True``，否则返回 ``False``。
    """

    await matcher.send(prompt)

    @waiter(waits=["message"], block=True)
    async def listen(event: Event) -> str:
        """读取用户确认消息。"""

        return event.get_message().extract_plain_text().strip().lower()

    response = await listen.wait(timeout=60)
    return response == "yes"


async def delete_classes_groups(classes_list: list[Classes]) -> None:
    """删除班级并清理关联群组与群设置。

    Args:
        classes_list: 需要级联删除的班级列表。
    """

    for classes in classes_list:
        group = classes.group
        settings = group.settings
        await classes.filter(id=classes.id).delete()
        await group.filter(id=group.id).delete()
        if settings is not None:
            await settings.filter(id=settings.id).delete()


async def get_school_or_finish(matcher: AlconnaMatcher, school_name: str) -> School:
    """根据学校名称获取学校对象。

    Args:
        matcher: 当前命令 matcher，用于在查询失败时结束会话。
        school_name: 用户输入的学校名称。

    Returns:
        School: 查询到的学校对象。
    """

    school_name = school_name.strip()
    school = await School.filter(name=school_name).first()
    if school is None:
        await matcher.finish(Emoji.error + f"学校`{school_name}`不存在！")
    return school


async def get_college_or_finish(matcher: AlconnaMatcher, school: School, college_name: str) -> College:
    """根据学校和学院名称获取学院对象。

    Args:
        matcher: 当前命令 matcher，用于在查询失败时结束会话。
        school: 学院所属学校对象。
        college_name: 用户输入的学院名称。

    Returns:
        College: 查询到的学院对象。
    """

    college_name = college_name.strip()
    college = await College.filter(name=college_name, school_id=school.id).first()
    if college is None:
        await matcher.finish(Emoji.error + f"学院`{college_name}`不存在于学校`{school.name}`下！")
    return college


async def get_major_or_finish(
    matcher: AlconnaMatcher,
    school: School,
    college: College,
    major_name: str,
) -> Major:
    """根据学校、学院和专业名称获取专业对象。

    Args:
        matcher: 当前命令 matcher，用于在查询失败时结束会话。
        school: 专业所属学校对象。
        college: 专业所属学院对象。
        major_name: 用户输入的专业名称。

    Returns:
        Major: 查询到的专业对象。
    """

    major_name = major_name.strip()
    major = await Major.filter(name=major_name, school_id=school.id, college_id=college.id).first()
    if major is None:
        await matcher.finish(Emoji.error + f"专业`{major_name}`不存在于学院`{college.name}`下！")
    return major


async def get_organization_or_finish(
    matcher: AlconnaMatcher,
    school: School,
    organization_name: str,
) -> Organization:
    """根据学校和组织名称获取唯一组织对象。

    Args:
        matcher: 当前命令 matcher，用于在查询失败或同名歧义时结束会话。
        school: 组织所属学校对象。
        organization_name: 用户输入的组织名称。

    Returns:
        Organization: 查询到的唯一组织对象。
    """

    organization_name = organization_name.strip()
    organizations = await Organization.filter(name=organization_name, school_id=school.id).all()
    if not organizations:
        await matcher.finish(Emoji.error + f"组织`{organization_name}`不存在于学校`{school.name}`下！")
    if len(organizations) > 1:
        organization_types = "、".join(get_organization_type_label(org.organization_type) for org in organizations)
        await matcher.finish(
            Emoji.error + f"学校`{school.name}`下存在多个同名组织`{organization_name}`，当前类型包括：{organization_types}"
        )
    return organizations[0]


async def resolve_identity(
    matcher: AlconnaMatcher,
    user: UserOrCreatedDepends,
    identity: str | None,
) -> tuple[str, object]:
    """解析当前用户操作组织成员关系时使用的身份。

    Args:
        matcher: 当前命令 matcher，用于在身份不合法时结束会话。
        user: 当前用户对象，可能绑定学生或教师身份。
        identity: 用户显式输入的身份名称。

    Returns:
        tuple[str, object]: 身份标识和对应的学生或教师对象。
    """

    if identity:
        identity = IDENTITY_MAPPING.get(identity.strip().lower())
        if identity is None:
            await matcher.finish(Emoji.error + "身份只支持：学生 或 教师")
    elif user.student and user.teacher:
        await matcher.finish(Emoji.error + "您同时具备学生和教师身份，请补充指定身份：学生 或 教师")
    elif user.student:
        identity = "student"
    elif user.teacher:
        identity = "teacher"
    else:
        await matcher.finish(Emoji.error + "您还没有绑定学生或教师身份，无法操作组织成员关系。")

    if identity == "student":
        if user.student is None:
            await matcher.finish(Emoji.error + "当前账号没有绑定学生身份。")
        return identity, user.student
    if user.teacher is None:
        await matcher.finish(Emoji.error + "当前账号没有绑定教师身份。")
    return "teacher", user.teacher
