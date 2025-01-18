import re

from nonebot.matcher import Matcher
from nonebot import logger, on_regex
from nonebot.params import EventPlainText
from nonebot.adapters import Event, ntchat
from nonebot_plugin_htmlrender import get_new_page
from nonebot_plugin_localstore import get_cache_dir
from nonebot_plugin_alconna import MsgTarget, UniMessage

template_dir = get_cache_dir("douyin")


download_url = "https://douyinxz.com/"
pattern_str = r"https://(?:www\.iesdouyin\.com/share/video/\d+|v\.douyin\.com/\w+)/?"
pattern = re.compile(pattern_str)
douyin_url_cmd = on_regex(pattern_str, priority=100)


@douyin_url_cmd.handle()
async def _(
    matcher: Matcher, target: MsgTarget, event: Event, text: str = EventPlainText()
):
    # 匹配链接
    video_url, img_url = None, None
    matches = pattern.findall(text)
    for match in matches:
        async with get_new_page() as new_page:
            await new_page.goto(
                download_url, timeout=120000, wait_until="domcontentloaded"
            )
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
            try:
                if isinstance(event, ntchat.MessageEvent):
                    await matcher.send(ntchat.MessageSegment.file(video_url))
                else:
                    await target.send(UniMessage.video(url=video_url))
            except Exception as e:
                logger.exception(e)
                await matcher.finish(video_url)
        elif img_url:
            await target.send(UniMessage.image(url=img_url))
