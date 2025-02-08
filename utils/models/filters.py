from typing import TYPE_CHECKING, Any, Type, Generic, TypeVar, Optional, Generator

from nonebot_plugin_orm import get_scoped_session
from sqlalchemy import (
    Select,
    ScalarResult,
    ColumnExpressionArgument,
    delete,
    select,
    update,
)

T = TypeVar("T")

if TYPE_CHECKING:

    class SelectFilter(Select, Generic[T]):
        def __await__(self) -> Generator[Any, Any, ScalarResult[T]]:
            ...

else:

    class SelectFilter(Generic[T]):
        def __init__(self, model) -> None:
            self.model: T = model
            self._select = select(model)

        def __getattr__(self: T, name: str) -> "T":
            call = getattr(self._select, name)

            def _(*args, **kwargs):
                self._select = call(*args, **kwargs)
                return self

            return _

        def __await__(self) -> Generator[Any, Any, ScalarResult[T]]:
            async def _():
                session = get_scoped_session()
                return await session.scalars(self._select)

            return _().__await__()


class Filter(Generic[T]):
    def __init__(
        self,
        model: Type[T],
        session=None,
        options: Optional[list[ColumnExpressionArgument[bool]]] = None,
    ) -> None:
        self.model: type[T] = model
        self.session = get_scoped_session() if session is None else session
        self.options: list[ColumnExpressionArgument[bool]] = (options or []).copy()

    def filter(
        self, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any
    ) -> "Filter[T]":
        self.options.extend(where_clause)
        select_option = None
        for key in kwargs:
            option = getattr(self.model, key) == kwargs[key]
            select_option = option if select_option is None else select_option & option
        if select_option is not None:
            self.options.append(select_option)
        return Filter[self.model](self.model, self.session, self.options)

    async def first(self) -> Optional[T]:
        return await self.session.scalar(select(self.model).where(*self.options))

    async def scalars(self) -> ScalarResult[T]:
        return await self.session.scalars(select(self.model).where(*self.options))

    async def delete(self):
        result = await self.session.execute(delete(self.model).where(*self.options))
        await self.session.commit()
        return result

    async def update(self, **kwargs: Any):
        result = await self.session.execute(
            update(self.model).where(*self.options).values(**kwargs)
        )
        await self.session.commit()
        return result

    async def all(self) -> list[T]:
        return list(await self.scalars())

    async def exists(self) -> bool:
        return bool(
            await self.session.scalar(
                select(select(self.model).where(*self.options).exists())
            )
        )


class FilterModel:
    @classmethod
    def filter(cls, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any):
        return Filter[cls](cls).filter(*where_clause, **kwargs)

    async def create(self):
        session = get_scoped_session()
        session.add(self)
        await session.commit()
        await session.refresh(self)
        return self

    async def update(self, **kwargs: Any):
        session = get_scoped_session()
        for key in kwargs:
            setattr(self, key, kwargs[key])
        await session.commit()
        await session.refresh(self)
        return self

    @classmethod
    @property
    def select(cls: type[T]) -> SelectFilter[T]:
        return SelectFilter[cls](cls)
