from lxml import etree

from ..typing import BaseSearchEngine, AnimePools, Anime, List


class SearchEngine(BaseSearchEngine):
    name: str = "动漫花园"
    base_url: str = "https://dmhy.anoneko.com"

    async def __call__(self, keyword: str) -> AnimePools:
        response = await self.client.get("/topics/list", params={"keyword": keyword})
        data: List[etree._Element] = etree.HTML(response.text, etree.HTMLParser()).xpath("//table[@class='tablesorter']//tbody//tr")
        return AnimePools([Anime(
            title=value.xpath("string(./td[@class='title'])").replace("\n", ""),
            tag=value.xpath("string(./td/a//font)"),
            magnet=value.xpath("string(./td/a[@class='download-arrow arrow-magnet']/@href)").split("&")[0],
            size=value.xpath("./td")[4].text,
        ) for value in data])