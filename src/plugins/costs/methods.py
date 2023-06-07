from pathlib import Path
from typing import Dict, List, Optional
from django.db.models.functions import Now
from django.db.models import Sum, Q
from pandas import DataFrame
from nonebot.rule import ArgumentParser

from utils.orm.models import ClassTable, ClassFunds, Student
from utils.auth import User
from utils.tools import html_to_image, query_date, run_sync
from utils.typing import BaseAuth
from utils.localstore import LocalStore

from .config import env

local_store = LocalStore("cost")


class AddCost(BaseAuth):
    @staticmethod
    def is_number(number: str) -> bool:
        try:
            float(number)
            return True
        except ValueError:
            return False

    async def add_cost(
        self, fee_type: str, fee_money: str, class_table: Optional[ClassTable] = None
    ) -> ClassFunds:
        if class_table is None and isinstance(self.user, Student):
            return await ClassFunds.objects.acreate(
                creator=self.user.qq,
                class_table=self.user.class_table,
                fee_type=fee_type,
                fee_money=fee_money,
                fee_time=Now(),
            )
        return await ClassFunds.objects.acreate(
            creator=self.user.qq,
            class_table=class_table,
            fee_type=fee_type,
            fee_money=fee_money,
            fee_time=Now(),
        )

    async def to_card(self, cost: ClassFunds) -> bytes:
        template = env.get_template("costcard.html")
        return await html_to_image(
            await template.render_async(
                class_name=cost.class_table.name, cost=cost
            )
        )


class ShowCost(BaseAuth):
    def __init__(self, user: User) -> None:
        super().__init__(user)
        self.query_date: dict = {}

    @staticmethod
    def per(v1: float, v2: float) -> float:
        try:
            v1 /= v2
            if v1 > 1:
                return 100.0
            return round(v1 * 100, 1)
        except ZeroDivisionError:
            return 0

    def set_date(self, string: str):
        print(query_date(string, "fee_time"))
        self.query_date = query_date(string, "fee_time")  # type: ignore

    async def show_cost(self, class_table: ClassTable):
        costs_list = []
        costs = ClassFunds.objects.filter(class_table=class_table)
        money = await costs.aaggregate(
            total_income=Sum("fee_money", filter=Q(fee_money__gt=0)),
            remaining=Sum("fee_money"),
        )
        money["total_expenditure"] = money["total_income"] - money["remaining"]
        money["expenditure_ratio"] = 0
        async for cost in costs.filter(**self.query_date):
            costs_list.append(cost)
            if cost.money < 0:
                money["expenditure_ratio"] += -cost.money
        template = env.get_template("costlist.html")
        return await html_to_image(
            await template.render_async(
                **self.query_date, **money, costs=costs_list, per=self.per, round=round
            )
        )


class ExportCost(ShowCost):
    async def export_cost(self, class_table: ClassTable) -> Path:
        cost_path = local_store.mkdir(str(class_table.group_id)).joinpath(
            "-".join(str(i) for i in self.query_date.values()) + "班费明细.xlsx"
        )
        DataFrame(
            [
                i.values()
                async for i in ClassFunds.objects.filter(
                    class_table=class_table, **self.query_date
                ).values(
                    "fee_id",
                    "fee_time",
                    "fee_money",
                    "creator",
                    "fee_type",
                )
            ],
            columns=[
                "账单ID",
                "支收时间",
                "消费金额",
                "记账人",
                "事由",
            ],
        ).to_excel(cost_path, index=False)
        return cost_path

    async def clear_file(self, file_path: Path):
        for i in file_path.iterdir():
            try:
                if "xlsx" in i.suffix:
                    await run_sync(i.unlink)()
            except PermissionError:
                ...
