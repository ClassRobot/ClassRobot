from typing import Optional, Tuple, Type, Dict

from ..typing import AnimePools, BaseSearchEngine
from ..config import global_config

from . import (
    anoneko,
    dongmanhuayuan
)

search_engines: Dict[str, Type[BaseSearchEngine]] = {
    "anoneko": anoneko.SearchEngine,
    "dongmanhuayuan": dongmanhuayuan.SearchEngine,
}


class SearchResources:
    _select: Optional[str] = None
    
    @classmethod
    def next_search_engine(cls) -> str:
        """切换到下一个搜索引擎,当最后一个搜索引擎也无法搜索到资源时会跳转回第一个搜索引擎"""
        keys = list(search_engines.keys())
        if cls._select in keys:
            index = keys.index(cls._select) + 1
            cls._select = keys[0 if index >= len(keys) else index]
        else:
            cls._select = keys[0]
        return cls._select
    
    @classmethod
    @property
    def select(cls) -> str:
        """选择搜索引擎"""
        if cls._select is None:
            return cls.next_search_engine()
        return cls._select
    
    @classmethod
    @property
    def SearchEngine(cls) -> Type[BaseSearchEngine]:
        return search_engines[cls.select]

    @classmethod
    async def search(cls, keyword: str) -> AnimePools:
        engine = cls.SearchEngine()
        return await engine(keyword)
