from __future__ import annotations

from src.shared.tools import StringCard
from src.core.auth import JoinMethodLang
from src.models import Classes, ClassesJoinRequest


def get_join_method_label(join_method: str | None) -> str:
    """返回班级加入方式的展示文案。

    Args:
        join_method: 班级加入方式枚举值或历史字符串。

    Returns:
        str: 面向用户展示的加入方式文案。
    """

    if join_method and join_method in JoinMethodLang._member_names_:
        return str(JoinMethodLang[join_method])
    return join_method or "未设置"


async def render_join_request_card(title: str, requests: list[ClassesJoinRequest]) -> str:
    """渲染入班申请卡片。

    Args:
        title: 卡片标题。
        requests: 待展示的入班申请列表。

    Returns:
        str: 渲染后的文本卡片。
    """

    card = StringCard(title)
    for request in requests:
        current_classes = request.user.student.classes.name if request.user.student else "未加入班级"
        (
            card.hr()
            .text(f"申请ID: {request.id}")
            .text(f"申请人: {request.user.nickname}")
            .text(f"目标班级: [{request.classes.id}] {request.classes.name}")
            .text(f"当前班级: {current_classes}")
            .text(f"申请方式: {get_join_method_label(request.join_method)}")
            .text(f"申请时间: {request.created_at.strftime('%Y-%m-%d %H:%M')}")
        )
        if request.describe:
            card.text(f"申请说明: {request.describe}")
    return card.render()


async def render_classes_card(title: str, classes_list: list[Classes]) -> str:
    """渲染班级信息卡片。

    Args:
        title: 卡片标题。
        classes_list: 待展示的班级列表。

    Returns:
        str: 渲染后的文本卡片。
    """

    card = StringCard(title)
    for classes in classes_list:
        school_name = classes.school.name if classes.school else "未设置"
        college_name = classes.college.name if classes.college else "未设置"
        major_name = classes.major_ref.name if classes.major_ref else (classes.major or "未设置")
        (
            card.hr()
            .text(f"班级ID: {classes.id}")
            .text(f"班级名称: {classes.name}")
            .text(f"学校: {school_name}")
            .text(f"学院: {college_name}")
            .text(f"专业: {major_name}")
            .text(f"学生数量: {await classes.student_count()}")
            .text(f"加入方式: {get_join_method_label(classes.group.settings.join_method)}")
        )
    return card.render()
