from typing import List, Union, Optional, Generator

from numpy import where
from pandas import DataFrame
from django.db.models import Q
from django.db.models.manager import BaseManager
from utils.models import Student, Teacher, ClassTable

# 学生表格用于搜索的列
find_columns = [
    "qq",
    "name",
    "sex",
    "student_id",
    "phone",
    "position",
    "dormitory",
    "wechat",
    "ethnic",
    "class_index",
    "email",
]


class FuzzySearch:
    """对用户进行模糊搜索"""

    def __init__(self, string: str):
        self.string: str = string
        self.raws: List[Union[str, int]] = []
        self.numbers: List[int] = []  # 参数里的数字
        self.strings: List[str] = []  # 字符串
        for i in string.split():
            if i.isdigit():
                i = int(i)
                self.numbers.append(i)
            else:
                self.strings.append(i)
            self.raws.append(i)

    async def find_student(
        self,
        class_table: Optional[ClassTable] = None,
        columns: Optional[list] = None,
        all_find: bool = False,
        *,
        table: Optional[BaseManager[Student]] = None,
    ) -> DataFrame:
        """查找学生

        Args:
            class_table (Optional[ClassTable], optional): 学生所在班级. Defaults to None.
                如果为None则表示所有班级学生
            columns (Optional[list], optional): 需要查找的列. Defaults to None.
                如果为None表示默认的列
            all_find (bool, optional): 进行全部列查找. Defaults to False.
                当为True时忽略columns进行全部搜索
            table (Optional[BaseManager[Student]]): 自定义的学生进行查找

        Returns:
            DataFrame: 学生数据
        """
        table = table or Student.objects
        if class_table is not None:
            table = table.filter(class_table=class_table)
        student = DataFrame([i async for i in table.values()])
        if student.empty:
            return student
        student["sex"] = where(student["sex"], "男", "女")
        student["dorm_master"] = where(student["dorm_master"], "寝室长", "不是寝室长")
        find_student = student if all_find else student[columns or find_columns]
        return student[find_student.isin(self.raws).any(axis=1)].reset_index(drop=True)

    async def find_teacher(self) -> DataFrame:
        """搜索教师

        Returns:
            BaseManager[Teacher]: 教师信息
        """
        return DataFrame(
            [
                i
                async for i in Teacher.objects.filter(
                    Q(qq__in=self.numbers)
                    | Q(phone__in=self.numbers)
                    | Q(name__in=self.strings)
                ).values()
            ]
        )

    def __iter__(self) -> Generator[Union[str, int], None, None]:
        yield from self.raws
