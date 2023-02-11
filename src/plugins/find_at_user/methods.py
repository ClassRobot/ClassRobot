from typing import List, Optional, Union
from pandas import DataFrame

from utils.orm.models import ClassTable, StudentInfo, Teacher
from utils.manages.finder import FuzzySearch
from utils.manages.config import base_info, more_info, all_info, BaseInfo, MoreInfo


class BaseFindUser:
    def __init__(self, string: str) -> None:
        self.fs = FuzzySearch(string)


class FindUser(BaseFindUser):
    max_length = 3  # 作为文字显示时的最大数量，超出则用图片
    base_show = [
        MoreInfo.class_index,
        BaseInfo.name,
        BaseInfo.qq,
    ]
    show = base_info | more_info
    show_keys = list(show.keys())   # 中文
    show_values = list(show.values())   # columns name
    show_reverse = dict(zip(show_values, show_keys))
    _columns: Optional[List[str]] = None
    
    @property
    def display_columns(self) -> List[str]:
        """输入的内容中是否有包含需要显示的列

        Returns:
            List[str]: 需要显示的列
        """
        if self._columns is None:
            self._columns = self.base_show.copy()
            if self.fs.strings:
                for key in (i for i in self.show_keys if i in self.fs.strings and i not in self._columns):
                    self._columns.append(key)
            self._columns = [all_info[i] for i in self._columns]
        return self._columns

    async def find_user(self, class_table: ClassTable):
        teachers = await self.fs.find_teacher()
        students = await self.fs.find_student(class_table)
        return "\n===\n".join(i for i in (self.student_to_string(students), self.teacher_to_string(teachers)) if i)

    def student_to_string(self, students: DataFrame) -> str:
        if not students.empty:
            students = students.loc[:, self.display_columns]
            students.rename(self.show_reverse, axis=1, inplace=True)
            return self.to_string(students)
        return ""

    def teacher_to_string(self, teachers: DataFrame) -> str:
        if not teachers.empty:
            teachers = teachers.loc[:, ["name", "qq", "phone"]]
            teachers.columns=["姓名", "QQ", "联系方式"]
            return self.to_string(teachers)
        return ""

    def to_string(self, data: DataFrame) -> str:
        return "\n---\n".join(
            "\n".join(
                f"{k}:{v}" for k, v in i.items()
            ) for i in data.to_dict("records")
        )

class FindAtUser(BaseFindUser):
    async def find_at_user(self, class_table: ClassTable) -> Optional[List[int]]:
        teachers = await self.fs.find_teacher()
        students = await self.fs.find_student(class_table)
        student_empty = students.empty
        teacher_empty = teachers.empty
        if student_empty and teacher_empty:
            return None
        elif student_empty:
            return teachers["qq"].to_list()
        elif teacher_empty:
            return students["qq"].to_list()
        return (teachers["qq"] + students["qq"]).to_list()
