from utils import Emoji
from nonebot.adapters import Event
from utils.tools import StringCard
from nonebot_plugin_waiter import waiter
from utils.models import School, College, Major, Classes, Organization, OrganizationMember
from nonebot_plugin_alconna import AlconnaMatcher
from utils.models.depends import UserOrCreatedDepends

from .commands import (
    add_school,
    set_school,
    delete_school,
    add_college,
    set_college,
    delete_college,
    add_major,
    set_major,
    delete_major,
    add_organization,
    set_organization,
    delete_organization,
    query_structure,
    query_organization,
    join_organization,
    exit_organization,
)

ORGANIZATION_TYPE_MAPPING = {
    "general": "general",
    "通用": "general",
    "departmental": "departmental",
    "院系": "departmental",
    "interest": "interest",
    "兴趣": "interest",
    "governance": "governance",
    "治理": "governance",
    "temporary": "temporary",
    "临时": "temporary",
    "class": "class",
    "班级": "class",
}

ORGANIZATION_TYPE_LABELS = {
    "general": "通用组织",
    "departmental": "院系组织",
    "interest": "兴趣组织",
    "governance": "治理组织",
    "temporary": "临时组织",
    "class": "班级组织",
}

IDENTITY_MAPPING = {
    "student": "student",
    "学生": "student",
    "teacher": "teacher",
    "教师": "teacher",
}

SCHOOL_UPDATE_FIELDS = {
    "name": ["名称", "学校名称"],
    "address": ["地址", "位置"],
    "description": ["描述", "说明", "简介"],
}

COLLEGE_UPDATE_FIELDS = {
    "name": ["名称", "学院名称"],
    "description": ["描述", "说明", "简介"],
}

MAJOR_UPDATE_FIELDS = {
    "name": ["名称", "专业名称"],
    "description": ["描述", "说明", "简介"],
}

ORGANIZATION_UPDATE_FIELDS = {
    "name": ["名称", "组织名称"],
    "organization_type": ["类型", "组织类型"],
    "description": ["描述", "说明", "简介"],
}


def get_organization_type_label(organization_type: str) -> str:
    """返回组织类型的展示文案。"""
    return ORGANIZATION_TYPE_LABELS.get(organization_type, organization_type)


def parse_update_values(values: list[str], mapping: dict[str, list[str]]) -> dict[str, str]:
    """解析 key=value 形式的更新字段。"""
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
    """确认危险操作。"""
    await matcher.send(prompt)

    @waiter(waits=["message"], block=True)
    async def listen(event: Event):
        """等待确认消息。"""
        return event.get_message().extract_plain_text().strip().lower()

    response = await listen.wait(timeout=60)
    return response == "yes"


async def delete_classes_groups(classes_list: list[Classes]):
    """删除班级时顺带删除关联群组，避免留下孤儿绑定。"""
    for classes in classes_list:
        group = classes.group
        settings = group.settings
        await classes.filter(id=classes.id).delete()
        await group.filter(id=group.id).delete()
        if settings is not None:
            await settings.filter(id=settings.id).delete()


async def get_school_or_finish(matcher: AlconnaMatcher, school_name: str) -> School:
    """解析学校对象。"""
    school_name = school_name.strip()
    school = await School.filter(name=school_name).first()
    if school is None:
        await matcher.finish(Emoji.error + f"学校`{school_name}`不存在！")
    return school


async def get_college_or_finish(matcher: AlconnaMatcher, school: School, college_name: str) -> College:
    """解析学院对象。"""
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
    """解析专业对象。"""
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
    """解析组织对象。"""
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
    """解析当前用户操作组织时使用的身份。"""
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


@add_school.handle()
async def _(matcher: AlconnaMatcher, school_name: str, address: str | None = None):
    """添加学校。"""
    school_name = school_name.strip()
    if await School.filter(name=school_name).exists():
        await matcher.finish(Emoji.error + "学校已存在！")
    await School(name=school_name, address=address.strip() if address else None).create()
    await matcher.finish(Emoji.success + f"学校**{school_name}**添加成功！")


@set_school.handle()
async def _(matcher: AlconnaMatcher, school_name: str, values: list[str]):
    """修改学校。"""
    school = await get_school_or_finish(matcher, school_name)
    try:
        options = parse_update_values(values, SCHOOL_UPDATE_FIELDS)
    except ValueError as error:
        await matcher.finish(Emoji.error + str(error))
    if not options:
        await matcher.finish(Emoji.error + "未找到可修改字段，支持：名称、地址、描述。")

    payload = {}
    new_name = options.get("name")
    if new_name and new_name != school.name:
        if await School.filter(name=new_name).exists():
            await matcher.finish(Emoji.error + f"学校`{new_name}`已存在！")
        payload["name"] = new_name
    if "address" in options and options["address"] != school.address:
        payload["address"] = options["address"]
    if "description" in options and options["description"] != school.description:
        payload["description"] = options["description"]

    if not payload:
        await matcher.finish(Emoji.warning + "学校信息没有变化。")

    school = await school.update(**payload)
    await matcher.finish(Emoji.success + f"学校`{school.name}`修改成功！")


@delete_school.handle()
async def _(matcher: AlconnaMatcher, school_name: str):
    """删除学校。"""
    school = await get_school_or_finish(matcher, school_name)
    college_count = await College.filter(school_id=school.id).count()
    major_count = await Major.filter(school_id=school.id).count()
    classes_list = await Classes.filter(school_id=school.id).all()
    organization_count = await Organization.filter(school_id=school.id).count()

    confirmed = await confirm_action(
        matcher,
        Emoji.warning
        + f"删除学校`{school.name}`将同时删除学院 {college_count} 个、专业 {major_count} 个、班级 {len(classes_list)} 个、组织 {organization_count} 个，是否继续？(yes/no)",
    )
    if not confirmed:
        await matcher.finish(Emoji.warning + "已取消操作。")

    await delete_classes_groups(classes_list)
    await school.delete()
    await matcher.finish(Emoji.success + f"学校`{school.name}`已删除。")


@add_college.handle()
async def _(matcher: AlconnaMatcher, school_name: str, college_name: str):
    """添加学院。"""
    school = await get_school_or_finish(matcher, school_name)
    college_name = college_name.strip()
    if await College.filter(name=college_name, school_id=school.id).exists():
        await matcher.finish(Emoji.error + f"**{college_name}**学院已存在！")
    await College(name=college_name, school_id=school.id).create()
    await matcher.finish(Emoji.success + f"学校`{school.name}`下的学院`{college_name}`添加成功！")


@set_college.handle()
async def _(matcher: AlconnaMatcher, school_name: str, college_name: str, values: list[str]):
    """修改学院。"""
    school = await get_school_or_finish(matcher, school_name)
    college = await get_college_or_finish(matcher, school, college_name)
    try:
        options = parse_update_values(values, COLLEGE_UPDATE_FIELDS)
    except ValueError as error:
        await matcher.finish(Emoji.error + str(error))
    if not options:
        await matcher.finish(Emoji.error + "未找到可修改字段，支持：名称、描述。")

    payload = {}
    new_name = options.get("name")
    if new_name and new_name != college.name:
        if await College.filter(name=new_name, school_id=school.id).exists():
            await matcher.finish(Emoji.error + f"学校`{school.name}`下已存在学院`{new_name}`！")
        payload["name"] = new_name
    if "description" in options and options["description"] != college.description:
        payload["description"] = options["description"]

    if not payload:
        await matcher.finish(Emoji.warning + "学院信息没有变化。")

    college = await college.update(**payload)
    await matcher.finish(Emoji.success + f"学院`{college.name}`修改成功！")


@delete_college.handle()
async def _(matcher: AlconnaMatcher, school_name: str, college_name: str):
    """删除学院。"""
    school = await get_school_or_finish(matcher, school_name)
    college = await get_college_or_finish(matcher, school, college_name)
    major_count = await Major.filter(college_id=college.id).count()
    classes_list = await Classes.filter(college_id=college.id).all()

    confirmed = await confirm_action(
        matcher,
        Emoji.warning
        + f"删除学院`{college.name}`将同时删除专业 {major_count} 个、班级 {len(classes_list)} 个，是否继续？(yes/no)",
    )
    if not confirmed:
        await matcher.finish(Emoji.warning + "已取消操作。")

    await delete_classes_groups(classes_list)
    await college.delete()
    await matcher.finish(Emoji.success + f"学院`{college.name}`已删除。")


@add_major.handle()
async def _(matcher: AlconnaMatcher, school_name: str, college_name: str, major_name: str):
    """添加专业。"""
    school = await get_school_or_finish(matcher, school_name)
    college = await get_college_or_finish(matcher, school, college_name)
    major_name = major_name.strip()
    if await Major.filter(name=major_name, college_id=college.id).exists():
        await matcher.finish(Emoji.error + f"专业`{major_name}`已存在于学院`{college.name}`下！")
    await Major(name=major_name, school_id=school.id, college_id=college.id).create()
    await matcher.finish(Emoji.success + f"学院`{college.name}`下的专业`{major_name}`添加成功！")


@set_major.handle()
async def _(matcher: AlconnaMatcher, school_name: str, college_name: str, major_name: str, values: list[str]):
    """修改专业。"""
    school = await get_school_or_finish(matcher, school_name)
    college = await get_college_or_finish(matcher, school, college_name)
    major = await get_major_or_finish(matcher, school, college, major_name)
    try:
        options = parse_update_values(values, MAJOR_UPDATE_FIELDS)
    except ValueError as error:
        await matcher.finish(Emoji.error + str(error))
    if not options:
        await matcher.finish(Emoji.error + "未找到可修改字段，支持：名称、描述。")

    payload = {}
    new_name = options.get("name")
    if new_name and new_name != major.name:
        if await Major.filter(name=new_name, college_id=college.id).exists():
            await matcher.finish(Emoji.error + f"学院`{college.name}`下已存在专业`{new_name}`！")
        payload["name"] = new_name
    if "description" in options and options["description"] != major.description:
        payload["description"] = options["description"]

    if not payload:
        await matcher.finish(Emoji.warning + "专业信息没有变化。")

    major = await major.update(**payload)
    await matcher.finish(Emoji.success + f"专业`{major.name}`修改成功！")


@delete_major.handle()
async def _(matcher: AlconnaMatcher, school_name: str, college_name: str, major_name: str):
    """删除专业。"""
    school = await get_school_or_finish(matcher, school_name)
    college = await get_college_or_finish(matcher, school, college_name)
    major = await get_major_or_finish(matcher, school, college, major_name)
    classes_list = await Classes.filter(major_id=major.id).all()

    confirmed = await confirm_action(
        matcher,
        Emoji.warning + f"删除专业`{major.name}`将同时删除关联班级 {len(classes_list)} 个，是否继续？(yes/no)",
    )
    if not confirmed:
        await matcher.finish(Emoji.warning + "已取消操作。")

    await delete_classes_groups(classes_list)
    await major.delete()
    await matcher.finish(Emoji.success + f"专业`{major.name}`已删除。")


@add_organization.handle()
async def _(
    matcher: AlconnaMatcher,
    school_name: str,
    organization_name: str,
    organization_type: str | None = None,
    description: str | None = None,
):
    """添加组织。"""
    school = await get_school_or_finish(matcher, school_name)
    organization_name = organization_name.strip()
    normalized_type = ORGANIZATION_TYPE_MAPPING.get((organization_type or "general").strip().lower())
    if normalized_type is None:
        await matcher.finish(Emoji.error + "组织类型只支持：general/departmental/interest/governance/temporary/class")
    if await Organization.filter(
        name=organization_name,
        school_id=school.id,
        organization_type=normalized_type,
    ).exists():
        await matcher.finish(Emoji.error + f"学校`{school.name}`下已存在同名同类型组织`{organization_name}`！")
    organization = await Organization(
        name=organization_name,
        school_id=school.id,
        organization_type=normalized_type,
        description=description.strip() if description else None,
    ).create()
    await matcher.finish(
        Emoji.success
        + f"组织`{organization.name}`添加成功！\n"
        + f"{Emoji.info}所属学校: {school.name}\n"
        + f"{Emoji.info}组织类型: {get_organization_type_label(organization.organization_type)}"
    )


@set_organization.handle()
async def _(matcher: AlconnaMatcher, school_name: str, organization_name: str, values: list[str]):
    """修改组织。"""
    school = await get_school_or_finish(matcher, school_name)
    organization = await get_organization_or_finish(matcher, school, organization_name)
    try:
        options = parse_update_values(values, ORGANIZATION_UPDATE_FIELDS)
    except ValueError as error:
        await matcher.finish(Emoji.error + str(error))
    if not options:
        await matcher.finish(Emoji.error + "未找到可修改字段，支持：名称、类型、描述。")

    payload = {}
    new_name = options.get("name", organization.name)
    new_type = organization.organization_type
    if "organization_type" in options:
        normalized_type = ORGANIZATION_TYPE_MAPPING.get(options["organization_type"].strip().lower())
        if normalized_type is None:
            await matcher.finish(Emoji.error + "组织类型只支持：general/departmental/interest/governance/temporary/class")
        new_type = normalized_type

    if new_name != organization.name or new_type != organization.organization_type:
        exists = await Organization.filter(name=new_name, school_id=school.id, organization_type=new_type).first()
        if exists is not None and exists.id != organization.id:
            await matcher.finish(Emoji.error + f"学校`{school.name}`下已存在同名同类型组织`{new_name}`！")
        if new_name != organization.name:
            payload["name"] = new_name
        if new_type != organization.organization_type:
            payload["organization_type"] = new_type

    if "description" in options and options["description"] != organization.description:
        payload["description"] = options["description"]

    if not payload:
        await matcher.finish(Emoji.warning + "组织信息没有变化。")

    organization = await organization.update(**payload)
    await matcher.finish(
        Emoji.success
        + f"组织`{organization.name}`修改成功！\n"
        + f"{Emoji.info}组织类型: {get_organization_type_label(organization.organization_type)}"
    )


@delete_organization.handle()
async def _(matcher: AlconnaMatcher, school_name: str, organization_name: str):
    """删除组织。"""
    school = await get_school_or_finish(matcher, school_name)
    organization = await get_organization_or_finish(matcher, school, organization_name)
    member_count = await OrganizationMember.filter(organization_id=organization.id).count()

    confirmed = await confirm_action(
        matcher,
        Emoji.warning + f"删除组织`{organization.name}`将同时删除成员关系 {member_count} 条，是否继续？(yes/no)",
    )
    if not confirmed:
        await matcher.finish(Emoji.warning + "已取消操作。")

    await organization.delete()
    await matcher.finish(Emoji.success + f"组织`{organization.name}`已删除。")


@query_structure.handle()
async def _(matcher: AlconnaMatcher, school_name: str | None = None):
    """查询组织架构。"""
    if not school_name:
        schools = await School.filter().all()
        if not schools:
            await matcher.finish(Emoji.warning + "当前还没有学校数据。")
        card = StringCard("学校列表")
        for school in schools:
            college_count = await College.filter(school_id=school.id).count()
            major_count = await Major.filter(school_id=school.id).count()
            classes_count = await Classes.filter(school_id=school.id).count()
            organization_count = await Organization.filter(school_id=school.id).count()
            (
                card.hr()
                .text(f"学校: {school.name}")
                .text(f"学院数量: {college_count}")
                .text(f"专业数量: {major_count}")
                .text(f"班级数量: {classes_count}")
                .text(f"组织数量: {organization_count}")
            )
        await matcher.finish(card.render())

    school = await get_school_or_finish(matcher, school_name)
    colleges = await College.filter(school_id=school.id).all()
    majors = await Major.filter(school_id=school.id).all()
    classes_list = await Classes.filter(school_id=school.id).all()
    organizations = await Organization.filter(school_id=school.id).all()

    card = StringCard(f"组织架构 | {school.name}")
    (
        card.text(f"学院数量: {len(colleges)}")
        .text(f"专业数量: {len(majors)}")
        .text(f"班级数量: {len(classes_list)}")
        .text(f"组织数量: {len(organizations)}")
    )

    for college in colleges:
        card.hr().text(f"[学院] {college.name}")
        college_majors = [major for major in majors if major.college_id == college.id]
        college_orphan_classes = [
            classes for classes in classes_list if classes.college_id == college.id and classes.major_id is None
        ]
        if not college_majors:
            card.text("  暂无专业")
            if college_orphan_classes:
                card.text("  班级: " + "、".join(classes.name for classes in college_orphan_classes))
            continue
        for major in college_majors:
            major_classes = [classes for classes in classes_list if classes.major_id == major.id]
            classes_names = "、".join(classes.name for classes in major_classes) if major_classes else "暂无班级"
            card.text(f"  [专业] {major.name}")
            card.text(f"    班级: {classes_names}")
        if college_orphan_classes:
            card.text("  [未关联专业班级]")
            card.text("    " + "、".join(classes.name for classes in college_orphan_classes))

    orphan_classes = [classes for classes in classes_list if classes.college_id is None]
    if orphan_classes:
        card.hr().text("[未归档班级]")
        for classes in orphan_classes:
            card.text(f"  {classes.name}")

    if organizations:
        card.hr().text("[组织列表]")
        for organization in organizations:
            member_count = await OrganizationMember.filter(organization_id=organization.id).count()
            card.text(
                f"  {organization.name} | {get_organization_type_label(organization.organization_type)} | 成员数 {member_count}"
            )

    await matcher.finish(card.render())


@query_organization.handle()
async def _(matcher: AlconnaMatcher, school_name: str | None = None, organization_name: str | None = None):
    """查询组织。"""
    if not school_name:
        schools = await School.filter().all()
        if not schools:
            await matcher.finish(Emoji.warning + "当前还没有学校数据。")
        card = StringCard("组织总览")
        for school in schools:
            count = await Organization.filter(school_id=school.id).count()
            card.hr().text(f"学校: {school.name}").text(f"组织数量: {count}")
        await matcher.finish(card.render())

    school = await get_school_or_finish(matcher, school_name)
    if not organization_name:
        organizations = await Organization.filter(school_id=school.id).all()
        if not organizations:
            await matcher.finish(Emoji.warning + f"学校`{school.name}`下还没有组织。")
        card = StringCard(f"组织列表 | {school.name}")
        for organization in organizations:
            member_count = await OrganizationMember.filter(organization_id=organization.id).count()
            (
                card.hr()
                .text(f"组织名称: {organization.name}")
                .text(f"组织类型: {get_organization_type_label(organization.organization_type)}")
                .text(f"成员数量: {member_count}")
            )
        await matcher.finish(card.render())

    organization = await get_organization_or_finish(matcher, school, organization_name)
    members = await OrganizationMember.filter(organization_id=organization.id).all()
    student_members = [member for member in members if member.student is not None]
    teacher_members = [member for member in members if member.teacher is not None]

    card = StringCard(f"组织详情 | {organization.name}")
    (
        card.text(f"学校: {school.name}")
        .text(f"组织类型: {get_organization_type_label(organization.organization_type)}")
        .text(f"学生成员数: {len(student_members)}")
        .text(f"教师成员数: {len(teacher_members)}")
    )
    if organization.description:
        card.text(f"说明: {organization.description}")
    if student_members:
        card.hr().text("[学生成员]")
        for member in student_members[:10]:
            suffix = f" ({member.position})" if member.position else ""
            card.text(f"  {member.student.name}{suffix}")
    if teacher_members:
        card.hr().text("[教师成员]")
        for member in teacher_members[:10]:
            suffix = f" ({member.position})" if member.position else ""
            card.text(f"  {member.teacher.name}{suffix}")
    if len(members) > 20:
        card.text("  ...成员较多，已截断展示")
    await matcher.finish(card.render())


@join_organization.handle()
async def _(
    matcher: AlconnaMatcher,
    school_name: str,
    organization_name: str,
    identity: str | None,
    position: str | None,
    user: UserOrCreatedDepends,
):
    """加入组织。"""
    school = await get_school_or_finish(matcher, school_name)
    organization = await get_organization_or_finish(matcher, school, organization_name)
    identity_name, subject = await resolve_identity(matcher, user, identity)
    position = position.strip() if position else None

    if identity_name == "student":
        member = await organization.add_student(subject, position)
    else:
        member = await organization.add_teacher(subject, position)

    suffix = f"\n{Emoji.info}组织岗位: {member.position}" if member.position else ""
    await matcher.finish(
        Emoji.success + f"已以{ '学生' if identity_name == 'student' else '教师' }身份加入组织`{organization.name}`！" + suffix
    )


@exit_organization.handle()
async def _(
    matcher: AlconnaMatcher,
    school_name: str,
    organization_name: str,
    identity: str | None,
    user: UserOrCreatedDepends,
):
    """退出组织。"""
    school = await get_school_or_finish(matcher, school_name)
    organization = await get_organization_or_finish(matcher, school, organization_name)
    identity_name, subject = await resolve_identity(matcher, user, identity)

    if identity_name == "student":
        member = await OrganizationMember.filter(organization_id=organization.id, student_id=subject.id).first()
    else:
        member = await OrganizationMember.filter(organization_id=organization.id, teacher_id=subject.id).first()

    if member is None:
        await matcher.finish(
            Emoji.error + f"您当前没有以{ '学生' if identity_name == 'student' else '教师' }身份加入组织`{organization.name}`。"
        )

    await member.delete()
    await matcher.finish(Emoji.success + f"已退出组织`{organization.name}`。")
