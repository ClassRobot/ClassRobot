from pprint import pprint

from httpx import AsyncClient

tiktokio = "http://localhost:3680/api/hybrid/video_data"


async def get_video_url(url: str) -> dict | None:
    result = {}
    async with AsyncClient(timeout=20000) as client:
        response = await client.get(tiktokio, params={"url": url, "minimal": False})
        data = response.json()
        video = data["data"]["video"]
        pprint(video)
        if video.get("play_addr"):
            result["video"] = video["play_addr"]["url_list"][0]
        if video.get("cover"):
            result["image"] = video["cover"]["url_list"][0]
        return result or None
