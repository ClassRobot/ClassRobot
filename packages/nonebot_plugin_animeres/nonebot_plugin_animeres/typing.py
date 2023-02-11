from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union, Sequence, overload, Generator
from abc import ABC, abstractmethod
from nonebot.adapters.onebot.v11 import Message
from urllib.parse import urlparse
from httpx import AsyncClient
from httpx._types import CookieTypes
from .config import global_config


class Anime(BaseModel):
    """动漫资源信息"""
    title: str                  # 标题
    tag: str                    # 用于分类的标签
    size: Optional[str] = None  # 大小
    link: Optional[str] = None  # 跳转链接
    magnet: str = ""            # 种子链接

    def format(self, cartoon_dict: Optional[Dict[str, Any]] = None) -> str:
        return global_config.cartoon_formant.format(
            **(
                self.dict() if cartoon_dict is None else cartoon_dict
            )
        )

    async def to_string(self, *_) -> str:
        return self.format()


class AnimePools:
    """动漫池,包含多个动漫资源的信息"""
    _keys: Optional[List[str]] = None

    def __init__(
        self,
        animes: Optional[Sequence[Anime]] = None,
        search_engine: Optional["BaseSearchEngine"] = None
    ):
        self.pools: List[Anime] = []
        self.tags: Dict[str, List[Anime]] = {}
        self.search_engine: Optional[BaseSearchEngine] = search_engine
        if animes is not None:
            self.add(*animes)

    @property
    def keys(self) -> List[str]:
        if self._keys is None:
            self._keys = list(self.tags.keys())
        return self._keys

    @property
    def one_skip(self) -> bool:
        """当番剧类型只有一个的时候，跳过选项

        Returns:
            bool: True表示跳过
        """
        return len(self.keys) == 1 and global_config.cartoon_oneskip

    def join(self, string: str) -> str:
        return string.join(i.format() for i in self.pools)

    def add(self, *animes: Anime):
        for anime in animes:
            self._keys = None
            self.pools.append(anime)
            self.tags.setdefault(anime.tag, []).append(anime)
    
    def get(self, key: Union[str, int]) -> Optional["AnimePools"]:
        try:
            key = self.keys[key] if isinstance(key, int) else key
            return self.new(self.tags[key])
        except (IndexError, KeyError):
            return None
    
    def new(self, animes: Sequence[Anime]) -> "AnimePools":
        return AnimePools(
            animes=animes,
            search_engine=self.search_engine,
        )
    
    async def forward_msg(
        self, 
        uin: int, 
        anime_pools: Optional["AnimePools"] = None,
        client: Optional[AsyncClient] = None
    ) -> List[Dict[str, Any]]:
        """合并转发

        Args:
            uin (int): 用户QQ
            anime_pools (Optional[Anime], optional): 多个资源. Defaults to None.

        Returns:
            List[dict]: 合并转发内容
        """
        return [{
            "type": "node",
            "data": {
                "name": "使用迅雷等bit软件下载",
                "uin": uin,
                "content": Message(await i.to_string(
                    self.search_engine
                ))
            }
        } for i in anime_pools or self]
    
    def __bool__(self) -> bool:
        return bool(self.pools)
    
    def __iter__(self) -> Generator[Anime, None, None]:
        yield from self.pools
    
    def __repr__(self) -> str:
        return repr(self.pools)
    
    @overload
    def __getitem__(self, value: int) -> Anime: ...
    @overload
    def __getitem__(self, value: slice) -> "AnimePools": ...
    @overload
    def __getitem__(self, value: str) -> "AnimePools": ...
    def __getitem__(self, value: Union[int, slice, str]) -> Union[Anime, "AnimePools"]:
        if isinstance(value, int):
            return self.pools[value]
        elif isinstance(value, str):
            return self.new(self.tags[value])
        return self.new(self.pools[value])


class BaseSearchEngine(ABC):
    name: str = ""
    timeout: int = 60
    base_url: str = ""
    trust_env: bool = True
    cookies: Optional[CookieTypes] = None
    headers: Optional[Dict[str, str]] = None
    proxy: Optional[str] = global_config.cartoon_proxy

    _client: Optional[AsyncClient] = None

    @classmethod
    def domain(cls):
        return urlparse(cls.base_url).scheme

    @property
    def client(self) -> AsyncClient:
        if self._client is None:
            self._client = AsyncClient(
                trust_env=self.trust_env,
                base_url=self.base_url,
                cookies=self.cookies,
                headers=self.headers,
                proxies=self.proxy,
                timeout=self.timeout,
            )
            print("create", self._client.is_closed)
        return self._client

    @abstractmethod
    async def __call__(self, keyword: str) -> AnimePools: ...



