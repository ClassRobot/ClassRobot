from __future__ import annotations

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
"""组织类型命令输入到数据库枚举值的映射表。"""

ORGANIZATION_TYPE_LABELS = {
    "general": "通用组织",
    "departmental": "院系组织",
    "interest": "兴趣组织",
    "governance": "治理组织",
    "temporary": "临时组织",
    "class": "班级组织",
}
"""组织类型数据库枚举值到用户展示文案的映射表。"""

IDENTITY_MAPPING = {
    "student": "student",
    "学生": "student",
    "teacher": "teacher",
    "教师": "teacher",
}
"""组织成员身份输入到内部身份标识的映射表。"""

SCHOOL_UPDATE_FIELDS = {
    "name": ["名称", "学校名称"],
    "address": ["地址", "位置"],
    "description": ["描述", "说明", "简介"],
}
"""学校可修改字段和用户输入别名。"""

COLLEGE_UPDATE_FIELDS = {
    "name": ["名称", "学院名称"],
    "description": ["描述", "说明", "简介"],
}
"""学院可修改字段和用户输入别名。"""

MAJOR_UPDATE_FIELDS = {
    "name": ["名称", "专业名称"],
    "description": ["描述", "说明", "简介"],
}
"""专业可修改字段和用户输入别名。"""

ORGANIZATION_UPDATE_FIELDS = {
    "name": ["名称", "组织名称"],
    "organization_type": ["类型", "组织类型"],
    "description": ["描述", "说明", "简介"],
}
"""组织可修改字段和用户输入别名。"""
