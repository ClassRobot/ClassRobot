from ..typing import BaseSearchEngine, AnimePools


class SearchEngine(BaseSearchEngine):
    name: str = "动漫花园"
    base_url: str = "https://www.dongmanhuayuan.com"

    async def __call__(self, keyword: str) -> AnimePools:
        ...
