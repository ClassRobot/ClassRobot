import re

from nonebot import on_regex
from utils.config import priority
from nonebot.params import EventPlainText
from nonebot_plugin_htmlrender import get_new_page
from nonebot_plugin_localstore import get_cache_dir
from nonebot_plugin_alconna import MsgTarget, UniMessage, SupportScope

template_dir = get_cache_dir("douyin")


download_url = "https://douyinxz.com/"
pattern_str = r"https://(?:www\.iesdouyin\.com/share/video/\d+|v\.douyin\.com/\w+)/?"
pattern = re.compile(pattern_str)
douyin_url_cmd = on_regex(pattern_str, priority=priority)


@douyin_url_cmd.handle()
async def _(
    target: MsgTarget,
    text: str = EventPlainText(),
):
    # 匹配链接
    print(target.adapter, target.platform, target.scope)
    video_url, img_url = None, None
    matches = pattern.findall(text)
    for match in matches:
        async with get_new_page() as new_page:
            await new_page.goto(download_url, timeout=120000, wait_until="domcontentloaded")
            if (input_url := await new_page.query_selector("#url")) is None:
                return
            await input_url.fill(match)
            if submit := await new_page.query_selector("#get"):
                await submit.click()
                if video := await new_page.query_selector("video"):
                    video_url = await video.get_attribute("src")
                elif img := await new_page.query_selector(".img-rounded"):
                    img_url = await img.get_attribute("src")
        if video_url:
            if target.scope == SupportScope.wechat:
                await target.send(UniMessage.file(url=video_url))
            else:
                await target.send(UniMessage.video(url=video_url))
        elif img_url:
            await target.send(UniMessage.image(url=img_url))
