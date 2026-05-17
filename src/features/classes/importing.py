from __future__ import annotations

from datetime import datetime
from typing import Any

from utils.models import User, Student, StudentExtra


def normalize_cell(value: Any) -> str | None:
    """将导入表格中的单元格值规范化为字符串。

    Args:
        value: 从表格读取到的原始单元格值。

    Returns:
        str | None: 清理后的字符串；空值或 NaN 返回 ``None``。
    """

    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, float):
        if value != value:
            return None
        if value.is_integer():
            return str(int(value))
    try:
        if value != value:
            return None
    except TypeError:
        pass
    return str(value).strip() or None


def normalize_datetime(value: Any) -> datetime | None:
    """将导入表格中的日期字段规范化为 ``datetime``。

    Args:
        value: 从表格读取到的日期原始值。

    Returns:
        datetime | None: 可解析时返回日期时间，否则返回 ``None``。
    """

    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()

    text = normalize_cell(value)
    if text is None:
        return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


async def get_student_by_student_code(student_code: str | None) -> Student | None:
    """通过学号查询学生对象。

    Args:
        student_code: 学号。

    Returns:
        Student | None: 命中时返回学生对象，否则返回 ``None``。
    """

    if student_code is None:
        return None
    extra = await StudentExtra.filter(student_code=student_code).first()
    return extra.student if extra else None


async def build_user_update_payload(user: User, row: dict[str, str | datetime | None]) -> tuple[dict, int]:
    """根据导入行构建用户更新字段，并统计被跳过的冲突字段。

    Args:
        user: 待更新的用户对象。
        row: 已规范化的导入行。

    Returns:
        tuple[dict, int]: 第一个元素是可安全更新的字段，第二个元素是手机号/邮箱冲突数量。
    """

    payload = {}
    skipped_conflicts = 0

    nickname = row.get("name")
    if nickname and nickname != user.nickname:
        payload["nickname"] = nickname

    gender = row.get("sex")
    if gender and gender != user.gender:
        payload["gender"] = gender

    birthday = row.get("birthday")
    if birthday and birthday != user.birthday:
        payload["birthday"] = birthday

    email = row.get("email")
    if email:
        exists = await User.filter(email=email).first()
        if exists is None or exists.id == user.id:
            if email != user.email:
                payload["email"] = email
        else:
            skipped_conflicts += 1

    phone = row.get("phone")
    if phone:
        exists = await User.filter(phone=phone).first()
        if exists is None or exists.id == user.id:
            if phone != user.phone:
                payload["phone"] = phone
        else:
            skipped_conflicts += 1

    return payload, skipped_conflicts
