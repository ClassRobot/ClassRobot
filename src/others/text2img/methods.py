from base64 import b64decode, b64encode
from typing import List, Optional
from httpx import AsyncClient
from pygtrans import Translate
from asyncio import get_event_loop, AbstractEventLoop
from nonebot.log import logger

from .config import BetaParams, FromImageParams


class TextToImage:
    main_url: str = "http://localhost:6969/generate-stream"
    translate_url: str = "https://xiaoapi.cn/API/fy.php"
    proxies={'https': 'http://localhost:1080'}

    def __init__(self, loop: Optional[AbstractEventLoop] = None):
        self.client = AsyncClient(timeout=None, verify=False)
        self.loop = get_event_loop() if loop is None else loop
        self.translate = Translate(proxies=self.proxies)

    async def translate_text(self, text: str) -> str:
        try:
            return (await self.loop.run_in_executor(None, self.translate.translate, text, "en")).translatedText
        except Exception as err:
            logger.exception(err)
            return (await self.client.post(self.translate_url, params={"msg": text})).text

    async def draw(self, text: str, from_image_url: Optional[List[str]] = None) -> bytes:
        from_image = b64encode((await self.client.get(from_image_url[0])).content).decode() if from_image_url else None
        response = await self.client.post(self.main_url, json=BetaParams(text) | FromImageParams(from_image))
        return b64decode(response.text.split()[-1][5:])
