from asyncio import wait
from base64 import b64encode

from filetype import guess
from filetype.types import IMAGE
from httpx import AsyncClient
from nonebot_plugin_alconna import Image, Text
from nonebot_plugin_htmlrender import get_new_page

from utils.config import global_config

base_url = "https://generativelanguage.googleapis.com/v1beta"
client = AsyncClient(base_url=base_url, proxy=global_config.global_proxy, timeout=600)


async def generate_image(items: list[Text | Image]):
    parts = []
    wait_images = []

    async def request_image(item: Image):
        if item.url is None:
            return
        image_response = await page.request.get(item.url)
        image_bytes = await image_response.body()
        image_b64 = b64encode(image_bytes).decode()
        mime_type = guess(image_bytes)
        if mime_type in IMAGE:
            parts.append({"inline_data": {"mime_type": mime_type.MIME, "data": image_b64}})

    async with get_new_page() as page:
        for item in items:
            if isinstance(item, Text):
                parts.append({"text": str(item)})
            elif isinstance(item, Image):
                wait_images.append(request_image(item))
        if wait_images:
            await wait(wait_images)
    response = await client.post(
        "/models/gemini-2.0-flash-exp-image-generation:generateContent",
        params={"key": global_config.googleapis_key},
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["Text", "Image"]},
        },
    )
    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"]
    except KeyError:
        raise ValueError(data)
