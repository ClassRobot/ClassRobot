from strenum import StrEnum


class UserRole(StrEnum):
    """用户角色"""

    user = "user"
    """普通用户"""
    admin = "admin"
    """管理员"""
    student = "student"
    """学生"""
    teacher = "teacher"
    """教师"""
    class_cadre = "class_cadre"
    """班干部"""


class UserRoleLang(StrEnum):
    """用户角色"""

    user = "普通用户"
    """普通用户"""

    admin = "管理员"
    """管理员"""


class TeacherRole(StrEnum):
    """教师角色"""

    counselor = "counselor"
    """辅导员"""

    homeroom = "homeroom"
    """班主任"""

    teacher = "teacher"
    """任课老师"""


class TeacherRoleLang(StrEnum):
    """教师角色"""

    counselor = "辅导员"
    """辅导员"""

    homeroom = "班主任"
    """班主任"""

    teacher = "任课老师"
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


class JoinMethod(StrEnum):
    """加入方式"""

    invite = "invite"
    """邀请加入"""

    apply = "apply"
    """申请加入"""

    direct = "direct"
    """直接通过"""


class JoinMethodLang(StrEnum):
    """加入方式"""

    invite = "邀请加入"
    """邀请加入"""

    apply = "申请加入"
    """申请加入"""

    direct = "直接通过"
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


class PoliticalStatusLang(StrEnum):
    """政治面貌"""

    party_member = "党员"
    """党员"""

    league_member = "团员"
    """团员"""

    mass = "群众"
    """群众"""

    other = "其他"
    """其他"""
