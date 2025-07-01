from strenum import StrEnum

# 校园用户中的身份


class StudentRoleLang(StrEnum):
    """学生角色"""

    monitor = "班长"
    """班长"""

    vice_monitor = "副班长"
    """副班长"""

    secretary = "团支书"
    """团支书"""

    study = "学习委员"
    """学习委员"""

    life = "生活委员"
    """生活委员"""

    sports = "体育委员"
    """体育委员"""

    organization = "组织委员"
    """组织委员"""

    mental = "心理委员"
    """心理委员"""

    publicity = "宣传委员"
    """宣传委员"""

    arts = "文艺委员"
    """文艺委员"""

    student = "学生"
    """学生"""
