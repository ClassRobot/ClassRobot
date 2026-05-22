from __future__ import annotations

from src.core.auth import JoinMethod

JOIN_METHOD_MAPPING = {
    "direct": JoinMethod.direct,
    "直接": JoinMethod.direct,
    "直接通过": JoinMethod.direct,
    "apply": JoinMethod.apply,
    "申请": JoinMethod.apply,
    "申请加入": JoinMethod.apply,
    "invite": JoinMethod.invite,
    "邀请": JoinMethod.invite,
    "邀请加入": JoinMethod.invite,
}
"""班级加入方式的用户输入映射表。"""

JOIN_REQUEST_ACTION_MAPPING = {
    "通过": "approve",
    "同意": "approve",
    "approve": "approve",
    "pass": "approve",
    "拒绝": "reject",
    "驳回": "reject",
    "reject": "reject",
}
"""入班申请处理动作的用户输入映射表。"""
