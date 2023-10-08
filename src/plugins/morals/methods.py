from pathlib import Path

from utils.auth import User
from utils.tools import query_date
from pandas import Series, DataFrame
from utils.localstore import LocalStore
from utils.auth.finder import FuzzySearch
from django.db.models.functions import Now
from utils.typings import BaseAuth, SaveFile
from utils.models import Student, ClassTable, MoralEducation

local_store = LocalStore("morals")


class AddMoral(BaseAuth):
    user: Student

    def __init__(self, user: User) -> None:
        super().__init__(user)
        self.text = ""
        self.save_file = SaveFile()
        self.save_file.local_store = local_store
        self.users = DataFrame()

    async def set_add_user(self, text: str):
        """为另外的同学添加

        Args:
            text (str): 学生的关键字
        """
        fs = FuzzySearch(text)
        self.users = await fs.find_student(self.user.class_table)

    def set_text(self, text: str) -> bool:
        """设置德育内容

        Args:
            text (str): 内容

        Returns:
            bool: 是否有内容
        """
        self.text = text
        return bool(self.text)

    async def add_moral(self):
        file, _ = self.save_file.first_file
        if self.users.empty:
            await MoralEducation.objects.acreate(
                class_table=self.user.class_table,
                explain_reason=self.text,
                student_name=self.user.name,
                student_id=self.user.student_id,
                qq=self.user.qq,
                log_time=Now(),
                file=file,
            )
            return self.user.name
        else:
            for _, row in self.users.iterrows():
                await MoralEducation.objects.acreate(
                    class_table=self.user.class_table,
                    explain_reason=self.text,
                    student_name=row["name"],
                    student_id=row["student_id"],
                    qq=row["qq"],
                    log_time=Now(),
                    file=file,
                )
        await self.save_file.save()
        return self.user.name if self.users.name.empty else " ".join(self.users.name)


class ExportMoral(BaseAuth):
    async def export_moral(self, class_table: ClassTable, text: str = "") -> Path:
        moral_store = local_store.mkdir(str(class_table.group_id))
        export_date: dict = query_date(text, "log_time")  # type: ignore
        file_name = moral_store.joinpath(
            "-".join(str(i) for i in export_date.values()) + "德育日志.xlsx"
        )
        moral_data = DataFrame(
            [
                i
                async for i in MoralEducation.objects.filter(
                    class_table=class_table, **export_date
                ).values(
                    "student_id",
                    "student_name",
                    "score_type",
                    "score",
                    "log_time",
                    "explain_reason",
                )
            ]
        )
        moral_data.columns = ["学号", "姓名", "附加分名称", "分数", "时间", "说明"]
        moral_data["说明"] = moral_data["时间"].dt.date.astype(str) + moral_data["说明"]
        moral_data.drop("时间", axis=1, inplace=True)
        moral_data.to_excel(file_name)
        return file_name
