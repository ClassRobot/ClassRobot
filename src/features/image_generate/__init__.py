from base64 import b64decode

from utils import Emoji
from nonebot import logger
from utils.tools.cos import upload_file
from core.llm.util import uni_message_to_contents
from core.agent.runtime.util import ChatSessionDepends
from nonebot_plugin_alconna import Text, Image, UniMessage, AlconnaMatcher

from .util import generate_image
from .commands import image_generate_cmd


@image_generate_cmd.handle()
async def _(matcher: AlconnaMatcher, values: list[Text | Image], session: ChatSessionDepends):
    """处理当前命令或事件逻辑。"""
    print(values)
    await matcher.send(Emoji.loading + "正在生成图片...")
    try:
        parts = await generate_image(values)
    except Exception as e:
        logger.exception(e)
        await matcher.finish(Emoji.error + "图片生成失败，可能有以下几个原因图片过大、格式不对或需求违规！")
    messages = UniMessage()
    for part in parts:
        if "text" in part:
            messages += UniMessage.text(part["text"])
        elif "inlineData" in part:
            url = await upload_file(b64decode(part["inlineData"]["data"]), "image/jpeg")
            messages += UniMessage.image(url=url)
    session.messages.assistant_message(uni_message_to_contents(messages))
    await matcher.finish(messages)
