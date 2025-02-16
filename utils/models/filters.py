from typing import TYPE_CHECKING, Any, Type, Generic, TypeVar, Optional, Generator

from nonebot_plugin_orm import Model, get_session
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

        async def first(self) -> Optional[T]:
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

        async def first(self) -> Optional[T]:
            async with get_session() as session:
                return await session.scalar(self._select)

        def __await__(self) -> Generator[Any, Any, ScalarResult[T]]:
            async def _():
                async with get_session() as session:
                    return await session.scalars(self._select)

            return _().__await__()


class Filter(Generic[T]):
    def __init__(
        self,
        model: Type[T],
        options: Optional[list[ColumnExpressionArgument[bool]]] = None,
    ) -> None:
        self.model: type[T] = model
        self.options: list[ColumnExpressionArgument[bool]] = (options or []).copy()
        self.refresh_model: list[Model] = []

    def filter(
        self, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any
    ) -> "Filter[T]":
        self.options.extend(where_clause)
        select_option = None
        for key in kwargs:
            option = getattr(self.model, key) == kwargs[key]
            select_option = option if select_option is None else select_option & option
            if isinstance(kwargs[key], Model):
                self.refresh_model.append(kwargs[key])
        if select_option is not None:
            self.options.append(select_option)
        return Filter[self.model](self.model, self.options)

    async def first(self) -> Optional[T]:
        async with get_session() as session:
            return await session.scalar(select(self.model).where(*self.options))

    async def scalars(self) -> ScalarResult[T]:
        async with get_session() as session:
            return await session.scalars(select(self.model).where(*self.options))

    async def delete(self):
        async with get_session() as session:
            result = await session.execute(delete(self.model).where(*self.options))
            await session.commit()
            for model in self.refresh_model:
                await session.refresh(model)
            return result

    async def update(self, **kwargs: Any):
        async with get_session() as session:
            result = await session.execute(
                update(self.model).where(*self.options).values(**kwargs)
            )
            await session.commit()
            for model in self.refresh_model:
                await session.refresh(model)
            return result

    async def all(self) -> list[T]:
        return list(await self.scalars())

    async def exists(self) -> bool:
        async with get_session() as session:
            return bool(
                await session.scalar(
                    select(select(self.model).where(*self.options).exists())
                )
            )


class FilterModel:
    @classmethod
    def filter(cls, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any):
        return Filter[cls](cls).filter(*where_clause, **kwargs)

    async def create(self):
        async with get_session() as session:
            session.add(self)
            await session.commit()
            await session.refresh(self)
            return self

    async def update(self, **kwargs: Any):
        refresh_model = []
        async with get_session() as session:
            for key in kwargs:
                print(key, kwargs[key])
                print(getattr(self, key))
                setattr(self, key, kwargs[key])
                if isinstance(kwargs[key], Model):
                    refresh_model.append(kwargs[key])
            print(getattr(self, key))
            await session.commit()
            await session.refresh(self)

            for model in refresh_model:
                await session.refresh(model)
            return self

    @classmethod
    @property
    def select(cls: type[T]) -> SelectFilter[T]:
        return SelectFilter[cls](cls)

    async def refresh(self):
        async with get_session() as session:
            await session.refresh(self)
            return self
