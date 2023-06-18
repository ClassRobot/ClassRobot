from typing import Optional

from nonebot import on_command
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

# from nonebot.adapters.onebot.v11.permission import Permission
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.adapters.onebot.v11 import (
    Bot,
    Message,
    MessageEvent,
    MessageSegment,
    GroupMessageEvent,
)

from .methods import TextToImage

cmd = on_command("图片生成", aliases={"画画", "绘画", "画一个"}, priority=100, block=True)
cn_cmd = on_command("中文绘画", aliases={"中文画画"}, priority=100, block=True)
status_cmd = on_command(
    "设置绘画", aliases={"设置画画"}, priority=100, block=True, permission=SUPERUSER
)

draw_status = True
user_id: Optional[int] = None
black_user = [2630162576]


def draw_image(is_translate: bool = False):
    async def _(
        bot: Bot, matcher: Matcher, event: MessageEvent, msg: Message = CommandArg()
    ):
        global user_id, draw_status
        # if event.user_id in black_user:
        #     await matcher.finish("你已经被列入画画黑名单了！")
        if user_id is None and draw_status:
            if text := msg.extract_plain_text():
                if any(i in text for i in ["nsfw", "naked"]):
                    if isinstance(event, GroupMessageEvent):
                        await bot.set_group_ban(
                            group_id=event.group_id,
                            user_id=event.user_id,
                            duration=60 * 60,
                        )
                        await matcher.finish("不能画一些奇怪的东西噢！")
                else:
                    user_id = event.user_id
                    image = None
                    try:
                        tti = TextToImage()
                        text = await tti.translate_text(text) if is_translate else text
                        await matcher.send(
                            "开始画画啦！" + (f"\n{text}" if is_translate else "")
                        )
                        image = MessageSegment.image(
                            await tti.draw(text, extract_image_urls(msg))
                        )
                    except Exception as e:
                        logger.exception(e)
                        await matcher.finish("出问题了，不会画画了！")
                    finally:
                        user_id = None
                    await matcher.finish(image if draw_status else None)
        else:
            await matcher.finish("我还在帮别人画呢，等我一分钟吧！" if draw_status else "现在不画画了呢！")

    return _


cmd.handle()(draw_image())
cn_cmd.handle()(draw_image(True))


@status_cmd.handle()
async def _(matcher: Matcher, msg: Message = CommandArg()):
    global draw_status
    if msg.extract_plain_text() in ["启动", "开启"]:
        draw_status = True
        await matcher.finish("好啦可以开始画画了。")
    draw_status = False
    await matcher.finish("不画了，下班！")
