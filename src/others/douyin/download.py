from httpx import AsyncClient

tiktokio = "https://douyin.wtf/api/hybrid/video_data"


async def get_video_url(url: str) -> str | None:
    async with AsyncClient(timeout=20000) as client:
        response = await client.get(tiktokio, params={"url": url})
        data = response.json()
        return data["data"]["video"]["bit_rate"][0]["play_addr"]["url_list"][0]
