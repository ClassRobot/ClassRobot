from strenum import StrEnum


class ClassCadre(StrEnum):
    cc = "班长"  # Class Captain
    yls = "团支书"  # Youth League Secretary
    sc = "学习委员"  # Study Committee Member
    oc = "组织委员"  # Organization Committee Member
    pc = "心理委员"  # Psychological Committee Member
    spc = "宣传委员"  # Propaganda Committee Member
    mc = "男生委员"  # Male Student Committee Member
    fc = "女生委员"  # Female Student Committee Member
    sec = "治保委员"  # Security Committee Member
    hc = "生卫委员"  # Health Committee Member
    ic = "权益委员"  # Interests Committee Member


# --------------------------------- 学生信息列 ---------------------------------
# 基本信息
class BaseInfo(StrEnum):
    qq = "QQ"
    sex = "性别"
    name: "BaseInfo" = "姓名"  # type: ignore
    position = "职位"
    dormitory = "寝室"
    student_id = "学号"
    phone = "联系方式"


# 其它信息
class MoreInfo(StrEnum):
    email = "邮箱"
    wechat = "微信"
    ethnic = "民族"
    class_index = "序号"
    dorm_master = "寝室长"


# 隐私信息
class PrivacyInfo(StrEnum):
    id_card = "身份证号"
