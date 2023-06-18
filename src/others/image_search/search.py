# from Pic import SauceNAO, Network
from re import compile
from urllib.parse import urlparse
from typing import List, Union, Optional

from httpx import AsyncClient
from nonebot.adapters.onebot.v11 import Message, MessageSegment

from .config import config, trace_query

ImageUrlOrBytes = Union[str, bytes]


def is_url(url: str):
    u = urlparse(url)
    return all((u.scheme, u.netloc))


def get_url(message: Message) -> Optional[str]:
    for msg in message:
        if url := msg.data.get("url"):
            return url
        elif is_url(msg.data.get("text", None)):
            return msg.data.get("text")


class Trace:
    base_url: str = "https://api.trace.moe"
    search_api: str = "/search?cutBorders"
    anilist_api: str = "/anilist"


class Ascii2d:
    token_compile = compile(r'name="csrf-token" content="(.*?)"')
    base_url: str = "https://ascii2d.net"


class ImageSearch:
    def __init__(self, image: Optional[ImageUrlOrBytes] = None, uin: int = 0):
        self.image = image
        self.uin = uin

    def forward_msg(
        self, name: str, image: str, text: str, uin: Optional[int] = None
    ) -> dict:
        return {
            "type": "node",
            "data": {
                "name": name,
                "uin": self.uin if uin is None else uin,
                "content": MessageSegment.image(image) + Message("\n" + text),
            },
        }

    async def saucenao(self, image: Optional[ImageUrlOrBytes] = None) -> List[dict]:
        ...

    # async def ascii2d(self, image: Optional[ImageUrlOrBytes] = None) -> List[dict]:
    #     if image := image or self.image:
    #         async with AsyncClient(base_url=Ascii2d.base_url,
    #             #                    headers={
    #             # "cookie": "_session_id=782e03399f3e59785495f1ec5fa6388e",
    #             # 'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="108", "Google Chrome";v="108"',
    #             # 'sec-ch-ua-mobile': '?0',
    #             # 'sec-ch-ua-platform': "Windows",
    #             # 'sec-fetch-dest': 'document',
    #             # 'sec-fetch-mode': 'navigate',
    #             # 'sec-fetch-site': 'none',
    #             # 'sec-fetch-user': '?1',
    #             # 'upgrade-insecure-requests': '1',
    #             # # 'accept-encoding': 'gzip, deflate, br',
    #             # 'accept-language': 'zh-CN,zh;q=0.9',
    #             # 'cache-control': 'max-age=0',
    #             # "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    #             # "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    #             # }, proxies="http://127.0.0.1:1080"
    #                                ) as client:
    #             response = await client.post("")
    #             print(response.url)
    #             print(response.text)
    #             # print(findall(Ascii2d.token_compile, (await client.get("/")).text))
    #     return []

    async def trace(self, image: Optional[ImageUrlOrBytes] = None) -> List[dict]:
        if image := image or self.image:
            async with AsyncClient(base_url=Trace.base_url, timeout=360) as client:
                response = await client.post(
                    Trace.search_api,
                    **(
                        {"params": {"cutBorders": "", "anilistInfo": "", "url": image}}
                        if isinstance(image, str)
                        else {
                            "params": {
                                "cutBorders": "",
                                "anilistInfo": "",
                            },
                            "data": image,
                        }
                    ),
                    headers={"content-type": "image/jpeg"},
                )
                result = response.json()
                return [
                    self.forward_msg(
                        "trace",
                        i["image"],
                        f'《{i["anilist"]["title"]["native"]}》\n' f'【{i["filename"]}】',
                    )
                    for i in result["result"][:5]
                    if not i["anilist"]["isAdult"]
                ]
        return []

    async def search(self, image: Optional[ImageUrlOrBytes] = None):
        ...
