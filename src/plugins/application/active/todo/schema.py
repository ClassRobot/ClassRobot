from __future__ import annotations

from datetime import datetime

from src.models.models import TodoStatus

# 待办状态的用户可见文案，集中维护，供解析与展示复用。
STATUS_LABELS: dict[TodoStatus, str] = {
    TodoStatus.pending: "待办",
    TodoStatus.done: "已完成",
    TodoStatus.cancelled: "已取消",
}

# 查询时允许的状态别名到枚举的映射，覆盖中文与英文常见写法。
STATUS_ALIASES: dict[str, TodoStatus] = {
    "待办": TodoStatus.pending,
    "待处理": TodoStatus.pending,
    "未完成": TodoStatus.pending,
    "pending": TodoStatus.pending,
    "已完成": TodoStatus.done,
    "完成": TodoStatus.done,
    "done": TodoStatus.done,
    "已取消": TodoStatus.cancelled,
    "取消": TodoStatus.cancelled,
    "cancelled": TodoStatus.cancelled,
}

# 表示“查询全部状态”的别名集合。
ALL_STATUS_ALIASES = {"全部", "所有", "all"}

# 支持的截止时间输入格式，从完整到简单依次尝试。
_DUE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%m-%d %H:%M",
    "%m-%d",
)


def normalize_text(raw: object) -> str:
    """把命令参数值归一化成去除多余空白的字符串。

    Args:
        raw: 原始参数值，可能是字符串、多值序列或 None。

    Returns:
        str: 归一化后的文本；无有效内容时返回空字符串。
    """

    if raw is None:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = " ".join(str(item) for item in raw)
    return " ".join(str(raw).split())


def coerce_status(status: object) -> TodoStatus:
    """把字符串或枚举值统一转换成 :class:`TodoStatus`。"""

    if isinstance(status, TodoStatus):
        return status
    return TodoStatus(str(status))


def status_label(status: object) -> str:
    """返回待办状态的用户可见文案。"""

    return STATUS_LABELS.get(coerce_status(status), str(status))


def resolve_query_status(raw: object) -> tuple[TodoStatus | None, str]:
    """解析查询命令的状态过滤值。

    空输入默认只看待处理项；``全部`` 表示不过滤；其余按别名映射。

    Args:
        raw: 用户或 Agent 传入的状态文案。

    Returns:
        tuple[TodoStatus | None, str]: ``(状态过滤, 列表标题)``；状态为
        ``None`` 表示查询全部状态。

    Raises:
        ValueError: 状态文案无法识别。
    """

    text = normalize_text(raw)
    if not text:
        return TodoStatus.pending, "您的待办（待处理）"
    if text in ALL_STATUS_ALIASES:
        return None, "您的全部待办"
    status = STATUS_ALIASES.get(text)
    if status is None:
        raise ValueError(f"无法识别的待办状态：{text}（可用：待办/已完成/已取消/全部）")
    return status, f"您的待办（{status_label(status)}）"


def _match_due_format(text: str) -> datetime | None:
    """按支持的格式尝试解析时间文本，无法解析时返回 ``None``。

    Args:
        text: 已归一化的时间文本。

    Returns:
        datetime | None: 解析出的时间；无法匹配任何格式时返回 ``None``。
    """

    for fmt in _DUE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # 不含年份的简写格式默认补全为当前年份。
        if "%Y" not in fmt:
            parsed = parsed.replace(year=datetime.now().year)
        return parsed
    return None


def parse_due_at(raw: object) -> datetime | None:
    """解析截止时间输入。

    Args:
        raw: 截止时间文案，可能是字符串或多值序列。

    Returns:
        datetime | None: 解析出的时间；为空时返回 ``None``。

    Raises:
        ValueError: 时间文案无法解析。
    """

    text = normalize_text(raw)
    if not text:
        return None
    parsed = _match_due_format(text)
    if parsed is None:
        raise ValueError(f"无法识别的时间格式：{text}（支持示例：2026-05-30 或 2026-05-30 14:00）")
    return parsed


def split_due_and_content(tokens: object) -> tuple[str, str]:
    """把“标题之后的尾部参数”拆分成截止时间与备注。

    用户在聊天里通常按 ``标题 日期 时间 备注`` 的顺序自然输入，且日期与
    时间之间存在空格。这里按 token 贪婪识别开头的时间：先尝试把前两个
    token 当作“日期 时间”，再尝试单个 token 当作日期，剩余文本统一作为
    备注，避免把 ``14:00`` 这类时间误当成备注。

    Args:
        tokens: 标题之后的尾部参数，可能是 token 列表、字符串或 ``None``。

    Returns:
        tuple[str, str]: ``(截止时间文本, 备注文本)``；缺失项为空字符串。
    """

    if tokens is None:
        items: list[str] = []
    elif isinstance(tokens, (list, tuple)):
        items = [str(item).strip() for item in tokens if str(item).strip()]
    else:
        items = [part for part in str(tokens).split() if part]

    if not items:
        return "", ""
    if len(items) >= 2 and _match_due_format(f"{items[0]} {items[1]}") is not None:
        return f"{items[0]} {items[1]}", " ".join(items[2:])
    if _match_due_format(items[0]) is not None:
        return items[0], " ".join(items[1:])
    return "", " ".join(items)
