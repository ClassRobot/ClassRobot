from dataclasses import dataclass, fields
from typing import Dict, List, Literal


@dataclass
class ClassCadre:
    cc: Literal["班长"] = "班长" # Class Captain
    vc: Literal["副班长"] = "副班长" # Vice-Captain
    yls: Literal["团支书"] = "团支书" # Youth League Secretary
    sc: Literal["学习委员"] = "学习委员" # Study Committee Member
    oc: Literal["组织委员"] = "组织委员" # Organization Committee Member
    pc: Literal["心理委员"] = "心理委员" # Psychological Committee Member
    spc: Literal["宣传委员"] = "宣传委员" # Propaganda Committee Member
    mc: Literal["男生委员"] = "男生委员" # Male Student Committee Member
    fc: Literal["女生委员"] = "女生委员" # Female Student Committee Member
    sec: Literal["治保委员"] = "治保委员" # Security Committee Member
    hc: Literal["生卫委员"] = "生卫委员" # Health Committee Member
    ic: Literal["权益委员"] = "权益委员" # Interests Committee Member

    @classmethod
    def to_list(cls) -> List[str]:
        return [f.default for f in fields(cls)] # type: ignore

    @classmethod
    def to_dict(cls) -> Dict[str, str]:
        return cls().__dict__


# --------------------------------- 学生信息列 ---------------------------------
# 基本信息
@dataclass
class BaseInfo:
    qq: Literal["QQ"] = "QQ"
    sex: Literal["性别"] = "性别"
    name: Literal["姓名"] = "姓名"
    position: Literal["职位"] = "职位"
    dormitory: Literal["寝室"] = "寝室"
    student_id: Literal["学号"] = "学号"
    phone: Literal["联系方式"] = "联系方式"


# 其它信息
@dataclass
class MoreInfo:
    email: Literal["邮箱"] = "邮箱"
    wechat: Literal["微信"] = "微信"
    ethnic: Literal["民族"] = "民族"
    class_index: Literal["序号"] = "序号"
    dorm_master: Literal["寝室长"] = "寝室长"


# 隐私信息
@dataclass
class PrivacyInfo:
    id_card: Literal["身份证号"] = "身份证号"


base_info = {v: i for i, v in BaseInfo().__dict__.items()}
more_info = {v: i for i, v in MoreInfo().__dict__.items()}
privacy_info = {v: i for i, v in PrivacyInfo().__dict__.items()}
all_info = base_info | more_info | privacy_info
