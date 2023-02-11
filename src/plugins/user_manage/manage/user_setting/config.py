from utils.manages.config import all_info


class ModifiableColumns:
    student = all_info.copy()
    teacher = {
        "姓名": "name",
        "联系方式": "phone"
    }
    teacher_modifiable = {
        "职位": student.pop("职位"),
        "学号": student.pop("学号"),
        "序号": student.pop("序号"),
        "寝室长": student.pop("寝室长"),
    }


ModifiableColumns.student.pop("QQ")

