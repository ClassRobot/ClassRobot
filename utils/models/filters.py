from typing import TYPE_CHECKING, Any, Type, Generic, TypeVar, Optional, Generator

from sqlalchemy.orm import Mapped
from sqlalchemy.exc import InvalidRequestError
from nonebot_plugin_orm import Model, get_session
from sqlalchemy import Select, ScalarResult, ColumnExpressionArgument, func, delete, select, update

from .columns import PrimaryKeyInteger

T = TypeVar("T")

if TYPE_CHECKING:

    class SelectFilter(Select, Generic[T]):
        """封装选择过滤过滤逻辑。"""

        def __await__(self) -> Generator[Any, Any, ScalarResult[T]]:
            """返回可等待对象。"""
            ...

        async def first(self) -> Optional[T]:
            """获取第一项结果。"""
            ...

else:

    class SelectFilter(Generic[T]):
        """封装选择过滤过滤逻辑。"""

        def __init__(self, model) -> None:
            """初始化实例。

            参数:
                model (Any): 模型。
            """
            self.model: T = model
            self._select = select(model)

        def __getattr__(self: T, name: str) -> "T":
            """实现 __getattr__ 特殊方法。

            参数:
                name (str): 名称。

            返回:
                'T': 返回处理结果。
            """
            call = getattr(self._select, name)

            def _(*args, **kwargs):
                """调用当前查询对象的方法并继续返回链式过滤器。"""
                self._select = call(*args, **kwargs)
                return self

            return _

        async def first(self) -> Optional[T]:
            """获取第一项结果。"""
            async with get_session() as session:
                return await session.scalar(self._select)

        def __await__(self) -> Generator[Any, Any, ScalarResult[T]]:
            """返回可等待对象。"""

            async def _():
                """执行当前查询并返回结果集合。"""
                async with get_session() as session:
                    return await session.scalars(self._select)

            return _().__await__()


class Filter(Generic[T]):
    """封装过滤过滤逻辑。"""

    def __init__(
        self,
        model: Type[T],
        options: Optional[list[ColumnExpressionArgument[bool]]] = None,
    ) -> None:
        """初始化实例。

        参数:
            model (Type[T]): 模型。
            options (Optional[list[ColumnExpressionArgument[bool]]]): options。
        """
        self.model: type[T] = model
        self.options: list[ColumnExpressionArgument[bool]] = (options or []).copy()
        self.refresh_model: list[Model] = []

    def filter(self, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any) -> "Filter[T]":
        """过滤当前数据。

        参数:
            where_clause (*ColumnExpressionArgument[bool]): whereclause。
            kwargs (**Any): 可变关键字参数。

        返回:
            'Filter[T]': 返回处理结果。
        """
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
        """获取第一项结果。"""
        async with get_session() as session:
            return await session.scalar(select(self.model).where(*self.options))

    async def scalars(self) -> ScalarResult[T]:
        """获取标量结果。"""
        async with get_session() as session:
            return await session.scalars(select(self.model).where(*self.options))

    async def delete(self):
        """删除当前数据。"""
        async with get_session() as session:
            result = await session.execute(delete(self.model).where(*self.options))
            await session.commit()
            for model in self.refresh_model:
                await session.refresh(model)
            return result

    async def update(self, **kwargs: Any):
        """更新当前数据。

        参数:
            kwargs (**Any): 可变关键字参数。
        """
        async with get_session() as session:
            result = await session.execute(update(self.model).where(*self.options).values(**kwargs))
            await session.commit()
            for model in self.refresh_model:
                await session.refresh(model)
            return result

    async def count(self) -> int:
        """统计数量。"""
        async with get_session() as session:
            return await session.scalar(select(func.count()).select_from(self.model).where(*self.options)) or 0

    async def all(self) -> list[T]:
        """获取全部结果。"""
        return list(await self.scalars())

    async def exists(self) -> bool:
        """判断是否存在。"""
        async with get_session() as session:
            return bool(await session.scalar(select(select(self.model).where(*self.options).exists())))


class FilterModel:
    """表示过滤模型模型。"""

    id: Mapped[PrimaryKeyInteger]

    def __init_subclass__(cls, **kwargs) -> None:
        """初始化子类。

        参数:
            kwargs (**Any): 可变关键字参数。
        """
        if not getattr(cls, "__tablename__", None):
            name = cls.__name__
            snake_case = "".join(["_" + c.lower() if c.isupper() else c for c in name]).lstrip("_")
            setattr(cls, "__tablename__", "bot_" + snake_case)
        return super().__init_subclass__(**kwargs)

    @classmethod
    def filter(cls, *where_clause: ColumnExpressionArgument[bool], **kwargs: Any):
        """过滤当前数据。

        参数:
            where_clause (*ColumnExpressionArgument[bool]): whereclause。
            kwargs (**Any): 可变关键字参数。
        """
        return Filter[cls](cls).filter(*where_clause, **kwargs)

    async def create(self):
        """创建当前数据。"""
        async with get_session() as session:
            session.add(self)
            await session.commit()
            await session.refresh(self)
            return self

    async def update(self, **kwargs: Any):
        """更新当前数据。

        参数:
            kwargs (**Any): 可变关键字参数。
        """
        await self.filter(id=self.id).update(**kwargs)
        return await self.filter(id=self.id).first()

    @classmethod
    @property
    def select(cls: type[T]) -> SelectFilter[T]:
        """选择当前数据。"""
        return SelectFilter[cls](cls)

    async def refresh(self):
        """刷新当前数据。"""
        try:
            async with get_session() as session:
                await session.refresh(self)
                return self
        except InvalidRequestError as e:
            print(f"Error refreshing model {self}: {e}")
            return self

    async def delete(self):
        """删除当前数据。"""
        async with get_session() as session:
            await session.delete(self)
            await session.commit()

    @classmethod
    async def build_create(cls, data: list[dict[str, Any] | Model]) -> list[Model]:
        """构建创建。

        参数:
            data (list[dict[str, Any] | Model]): data。

        返回:
            list[Model]: 返回处理结果。
        """
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
        """构建删除。

        参数:
            data (list[Model]): data。
        """
        async with get_session() as session:
            for model in data:
                await session.delete(model)
            try:
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
