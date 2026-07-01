from __future__ import annotations

from src.models import Student
from src.shared.tools import StringCard
from src.core.auth import StudentRoleLang


async def render_student_card(student: Student) -> str:
    """渲染学生信息卡片。

    Args:
        student: 需要展示的学生对象。

    Returns:
        str: 渲染后的学生信息文本卡片。
    """

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

    return card.render()
