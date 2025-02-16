from strenum import StrEnum


class CurriculumType(StrEnum):
    """课表类型"""

    share = "share"
    """共享课表"""
    classes = "classes"
    """班级课表"""
    private = "private"
    """私人课表"""
    today = "today"
    """今日课表"""
