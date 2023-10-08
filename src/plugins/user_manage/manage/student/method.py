from typing import List

from pandas import DataFrame
from utils.models import Student, Teacher, ClassTable
from nonebot_plugin_orm import get_session
from .config import all_info, base_info


class AddStudent:
    def __init__(self, info: dict) -> None:
        info["sex"] = int(info["sex"] == "男")
        self.info = info | {"dorm_master": 0}

    async def insert(self, teacher: Teacher, class_table: ClassTable):
        async with get_session() as session:
            student = Student(
                **self.info,
                teacher=teacher,
                class_table=class_table,
            )
            session.add(student)
            return student


class BatchImportStudents:
    def __init__(self, data: DataFrame):
        data.rename(columns=all_info, inplace=True)
        self.data: DataFrame = DataFrame(
            data[[i for i in all_info.values() if i in data.columns]]
        )
        self.revise()

    def check_base_columns(self) -> List[str]:
        """检查基本需要的信息是否齐全

        Returns:
            List[str]: 缺少的基本列
        """
        return [i[0] for i in base_info.items() if i[1] not in self.data.columns]

    def revise(self):
        """修复数据中缺失数据和不全面数据"""
        self.setdefault("dorm_master", 0, lambda x: int(x == "是"))
        self.setdefault("class_index", range(1, self.data.shape[0] + 1))

    def setdefault(self, key: str, default, callback=None):
        """设置数据中可能不存在的列

        Args:
            key (str): 列名
            default (Any): 如果不存在则设置为默认值
            callback (Any, optional): 如果存在则执行回调. Defaults to None.
        """
        if key not in self.data.columns:
            self.data[key] = default
        elif callback is not None:
            self.data[key] = self.data[key].apply(callback)

    def check_missing_value(self) -> DataFrame:
        """检查缺少的内容

        Returns:
            DataFrame: 缺少的内容
        """
        base_columns = list(base_info.values())
        data = self.data[base_columns]
        missing = data[data.isna().any(axis=1)]
        return missing

    async def insert(self, teacher: Teacher, class_table: ClassTable):
        """写入数据

        Args:
            teacher (Teacher): 教师信息
            class_table (ClassTable): 班级信息
        """
        await Student.objects.filter(class_table=class_table).adelete()  # 删除之前的学生
        await Student.objects.abulk_create(
            Student(teacher=teacher, class_table=class_table, **value)  # type: ignore
            for value in self.data.to_dict("records")
        )  # 写入新学生数据
