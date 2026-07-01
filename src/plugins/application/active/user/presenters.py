from __future__ import annotations

from src.models import User
from src.shared.tools import StringCard
from src.core.auth import StudentRoleLang


async def render_user_card(user: User) -> str:
    """渲染用户信息卡片。

    Args:
        user: 需要展示的用户对象。

    Returns:
        str: 渲染后的用户信息文本卡片。
    """

    roles_text = "、".join(user.roles)
    organizations = await user.get_organizations()
    organization_names = "、".join(organization.name for organization in organizations) if organizations else "暂无"

    card = (
        StringCard()
        .hr("用户信息")
        .text(f"UID: {user.id}")
        .text(f"昵称: {user.nickname}")
        .text(f"账号: {user.username}")
        .text(f"当前角色: {roles_text}")
    )
    if user.email:
        card.text(f"邮箱: {user.email}")
    if user.phone:
        card.text(f"电话: {user.phone}")
    card.text(f"创建日期: {user.created_at.strftime('%Y-%m-%d')}")
    card.text(f"所属组织: {organization_names}")

    if user.teacher is not None:
        school_name = user.teacher.school.name if user.teacher.school else "未设置"
        college_name = user.teacher.college.name if user.teacher.college else "未设置"
        card.hr("教师信息")
        card.text(f"教师ID: {user.teacher.id}")
        card.text(f"教师昵称: {user.teacher.name}")
        card.text(f"归属学校: {school_name}")
        card.text(f"归属学院: {college_name}")
        card.text(f"班级数量: {len(user.teacher.classes)}")
        card.text(f"创建日期: {user.teacher.created_at.strftime('%Y-%m-%d')}")

    if user.student is not None:
        school_name = user.student.school.name if user.student.school else "未设置"
        major_name = (
            user.student.classes.major_ref.name
            if user.student.classes.major_ref
            else (user.student.classes.major or "未设置")
        )
        card.hr("学生信息")
        card.text(f"学生ID: {user.student.id}")
        card.text(f"学生昵称: {user.student.name}")
        card.text(f"归属学校: {school_name}")

        if user.student.role in StudentRoleLang._member_names_:
            card.text(f"学生职位: {StudentRoleLang[user.student.role]}")
        else:
            card.text(f"学生职位: {user.student.role}(无效)")

        card.text(f"班级ID: {user.student.classes.id}")
        card.text(f"班级名称: {user.student.classes.name}")
        card.text(f"专业名称: {major_name}")
        card.text(f"创建日期: {user.student.created_at.strftime('%Y-%m-%d')}")

    return card.render()
