import re

from utils import Emoji
from utils.config import priority
from nonebot import logger, on_regex
from nonebot.params import EventPlainText
from nonebot_plugin_localstore import get_cache_dir
from nonebot_plugin_alconna import MsgTarget, UniMessage, SupportScope

from .download import get_video_url

template_dir = get_cache_dir("douyin")

pattern_str = r"https://(?:www\.iesdouyin\.com/share/video/[\d-]+|v\.douyin\.com/[\w-]+)/?"
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
    if matches:
        await target.send(Emoji.success + "正在解析视频，请稍等...")
    for match in matches:
        try:
            if not video_url and not img_url and (data := await get_video_url(match)):
                video_url = data.get("video")
                img_url = data.get("image")
        except Exception as e:
            logger.exception(e)

        print(video_url)

        try:
            if video_url:
                if target.scope == SupportScope.wechat:
                    await target.send(UniMessage.file(url=video_url))
                else:
                    await target.send(UniMessage.video(url=video_url))
            elif img_url:
                await target.send(UniMessage.image(url=img_url))
            else:
                await target.send(Emoji.error + "解析失败,可能视频过大或者链接无效！")
        except Exception as e:
            logger.exception(e)
            await target.send(Emoji.error + "可能由于视频过大，发送失败")
