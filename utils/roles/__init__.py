from strenum import StrEnum

from .school import StudentRoleLang as StudentRoleLang


class UserRole(StrEnum):
    """用户角色"""

    user = "user"
    """用户"""
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

    user = "用户"
    """用户"""

    admin = "管理员"
    """管理员"""

    teacher = "教师"
    """教师"""

    student = "学生"
    """学生"""


class LeaveStatus(StrEnum):
    """请假状态"""

    leave = "leave"
    """请假中"""

    leave_pass = "leave_pass"
    """请假通过"""

    leave_reject = "leave_reject"
    """请假拒绝"""

    leave_pending = "leave_pending"
    """请假申请中"""


class TeacherRole(StrEnum):
    """教师角色"""

    teacher = "teacher"
    """老师"""


class TeacherRoleLang(StrEnum):
    """教师角色"""

    counselor = "辅导员"
    """辅导员"""

    homeroom = "班主任"
    """班主任"""

    teacher = "任课老师"
    """任课老师"""


class TeacherClassesRole(StrEnum):
    """教师在班级角色"""

    counselor = "counselor"
    """辅导员"""

    homeroom = "homeroom"
    """班主任"""

    teacher = "teacher"
    """任课老师"""


class CollegeTeacherRole(StrEnum):
    """教师在学院中的管理岗位"""

    manager = "manager"
    """学院负责人"""


class CollegeTeacherRoleLang(StrEnum):
    """教师在学院中的管理岗位中文名称"""

    manager = "学院负责人"
    """学院负责人"""


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

    assistant = "assistant"
    """班助/助教"""

    student = "student"
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
