from httpx import AsyncClient

tiktokio = "http://localhost:3680/api/hybrid/video_data"


async def get_video_url(url: str) -> dict | None:
    """获取视频链接。"""
    result = {}
    async with AsyncClient(timeout=20000) as client:
        response = await client.get(tiktokio, params={"url": url, "minimal": False})
        data = response.json()
        video = data["data"]["video"]
        if video.get("play_addr"):
            result["video"] = video["play_addr"]["url_list"][-1]
        if video.get("cover"):
            result["image"] = video["cover"]["url_list"][0]
        return result or None
