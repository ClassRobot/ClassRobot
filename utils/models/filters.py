from typing import TYPE_CHECKING, Any, Type, Generic, TypeVar, Optional, Generator

from sqlalchemy.orm import Mapped
from sqlalchemy.exc import InvalidRequestError
from nonebot_plugin_orm import Model, get_session
from sqlalchemy import Select, ScalarResult, ColumnExpressionArgument, func, delete, select, update

from .columns import PrimaryKeyInteger

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

    def filter(self, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any) -> "Filter[T]":
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
            result = await session.execute(update(self.model).where(*self.options).values(**kwargs))
            await session.commit()
            for model in self.refresh_model:
                await session.refresh(model)
            return result

    async def count(self) -> int:
        async with get_session() as session:
            return await session.scalar(select(func.count()).select_from(self.model).where(*self.options)) or 0

    async def all(self) -> list[T]:
        return list(await self.scalars())

    async def exists(self) -> bool:
        async with get_session() as session:
            return bool(await session.scalar(select(select(self.model).where(*self.options).exists())))


class FilterModel:
    id: Mapped[PrimaryKeyInteger]

    def __init_subclass__(cls, **kwargs) -> None:
        if not getattr(cls, "__tablename__", None):
            name = cls.__name__
            snake_case = "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")
            setattr(cls, "__tablename__", "bot_" + snake_case)
        return super().__init_subclass__(**kwargs)

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
        await self.filter(id=self.id).update(**kwargs)
        return await self.filter(id=self.id).first()

    @classmethod
    @property
    def select(cls: type[T]) -> SelectFilter[T]:
        return SelectFilter[cls](cls)

    async def refresh(self):
        try:
            async with get_session() as session:
                await session.refresh(self)
                return self
        except InvalidRequestError as e:
            print(f"Error refreshing model {self}: {e}")
            return self

    async def delete(self):
        async with get_session() as session:
            await session.delete(self)
            await session.commit()

    @classmethod
    async def build_create(cls, data: list[dict[str, Any] | Model]) -> list[Model]:
        models: list[Model] = []
        async with get_session() as session:
            for item in data:
                if isinstance(item, dict):
                    model = cls(**item)
                else:
                    model = item
                if not isinstance(model, Model):
                    raise TypeError(f"Invalid model type: {type(model)}")
                session.add(model)
                models.append(model)
            if models:
                try:
                    await session.commit()
                except Exception as e:
                    await session.rollback()
                    raise e
                for model in models:
                    await session.refresh(model)
        return models

    @classmethod
    async def build_delete(cls, data: list[Model]):
        async with get_session() as session:
            for model in data:
                await session.delete(model)
            try:
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
