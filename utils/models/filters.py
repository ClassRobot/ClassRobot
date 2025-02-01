from typing import Any, Type, Tuple, Generic, TypeVar, Optional

from nonebot_plugin_orm import get_scoped_session
from sqlalchemy import Select, ScalarResult, ColumnExpressionArgument, select

T = TypeVar("T")


class Filter(Generic[T]):
    def __init__(
        self, model: Type[T], session=None, where: Optional[Select[Tuple[T]]] = None
    ) -> None:
        self.model: type[T] = model
        self.session = get_scoped_session() if session is None else session
        self.where: Select[Tuple[T]] = select(model) if where is None else where

    def filter(
        self, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any
    ) -> "Filter[T]":
        select_option = None
        for key in kwargs:
            option = getattr(self.model, key) == kwargs[key]
            select_option = option if select_option is None else select_option & option
        self.where = self.where.where(*where_clause)
        if select_option is not None:
            self.where = self.where.where(select_option)
        return Filter[self.model](self.model, self.session, self.where)

    async def first(self) -> Optional[T]:
        return await self.session.scalar(self.where)

    async def scalars(self) -> ScalarResult[T]:
        return await self.session.scalars(self.where)


class FilterModel:
    @classmethod
    def filter(cls, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any):
        return Filter[cls](cls).filter(*where_clause, **kwargs)
