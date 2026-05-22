from __future__ import annotations

from src.models import Teacher
from src.shared.tools import StringCard


async def render_teacher_card(teacher: Teacher) -> str:
    """渲染教师信息卡片。

    Args:
        teacher: 需要展示的教师对象。

    Returns:
        str: 渲染后的教师信息文本卡片。
    """

    school_name = teacher.school.name if teacher.school else "未设置"
    college_name = teacher.college.name if teacher.college else "未设置"
    organizations = await teacher.get_organizations()
    organization_names = "、".join(organization.name for organization in organizations) if organizations else "暂无"

    card = (
        StringCard("教师信息")
        .text(f"教师ID: {teacher.id}")
        .text(f"姓名: {teacher.name}")
        .text(f"归属学校: {school_name}")
        .text(f"归属学院: {college_name}")
        .text(f"管理班级数: {len(teacher.classes)}")
        .text(f"所属组织: {organization_names}")
        .text(f"创建日期: {teacher.created_at.strftime('%Y-%m-%d')}")
    )

    if teacher.classes:
        card.hr("管理班级")
        for classes in teacher.classes[:10]:
            card.text(f"{classes.id}: {classes.name}")
        if len(teacher.classes) > 10:
            card.text("...班级较多，已截断展示")

    return card.render()
