from strenum import StrEnum


class UserRole(StrEnum):
    """用户角色"""

    user = "user"
    """普通用户"""
    admin = "admin"
    """管理员"""


class TeacherRole(StrEnum):
    """教师角色"""

    counselor = "counselor"
    """辅导员"""

    homeroom = "homeroom"
    """班主任"""

    teacher = "teacher"
    """任课老师"""


class StudentRole(StrEnum):
    """学生角色"""

    monitor = "monitor"
    """班长"""

    vice_monitor = "vice_monitor"
    """副班长"""

    secretary = "secretary"
    """团支书"""

    study = "study"
    """学习委员"""

    life = "life"
    """生活委员"""

    sports = "sports"
    """体育委员"""

    organization = "organization"
    """组织委员"""

    mental = "mental"
    """心理委员"""

    publicity = "publicity"
    """宣传委员"""

    arts = "arts"
    """文艺委员"""

    student = "student"
    """学生"""


class JoinMethod(StrEnum):
    """加入方式"""

    invite = "invite"
    """邀请"""

    apply = "apply"
    """申请"""

    direct = "direct"
    """直接通过"""


class PoliticalStatus(StrEnum):
    """政治面貌"""

    party_member = "PartyMember"
    """党员"""

    league_member = "LeagueMember"
    """团员"""

    mass = "mass"
    """群众"""

    other = "other"
    """其他"""
