from asyncio import sleep

from utils.orm import Student
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.params import Arg, CommandArg
from utils.auth import USER, STUDENT, User
from utils.tools.docs_sheet import re_docs
from utils.auth.config import base_info, more_info
from nonebot.adapters.onebot.v11.helpers import extract_image_urls
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment, GroupMessageEvent

from .methods import Watermark, NotWriteExcel
from .commands import rename, reset_index, add_watermark, excel_not_write

rename_columns = base_info | more_info


# --------------------------------- 群内同学重命名 ---------------------------------
@rename.handle()
async def _(
    matcher: Matcher,
    bot: Bot,
    event: GroupMessageEvent,
    msg: Message = CommandArg(),
    _: User = USER,
):
    bot_info = await bot.get_group_member_info(
        group_id=event.group_id, user_id=int(bot.self_id)
    )
    if bot_info["role"] != "member":
        text = msg.extract_plain_text()
        _rename = [rename_columns[i] for i in text.split() if i in rename_columns] or [
            "name",
            "dormitory",
            "phone",
        ]
        if not _rename:
            await matcher.finish(f"将{text}作为名字")
        await matcher.send("让我看看有谁要改！！")
        for name, user_id in (
            (i["card"], i["user_id"])
            for i in await bot.get_group_member_list(group_id=event.group_id)
        ):
            if (
                user := await Student.objects.filter(qq=user_id)
                .values(*_rename)
                .afirst()
            ):
                newname = " ".join(str(i) for i in user.values())
                if newname not in name:
                    await sleep(3)
                    await bot.set_group_card(
                        group_id=event.group_id, user_id=user_id, card=newname
                    )
        await matcher.finish("改完啦！")
    await matcher.finish("啊！我不是管理不能改名！")


# --------------------------------- 未填写 ---------------------------------
@excel_not_write.handle()
async def _(matcher: Matcher, msg: Message = CommandArg(), _: User = USER):
    if url := re_docs(str(msg)):
        matcher.set_arg("url", Message(url))


@excel_not_write.got("url")
async def _(matcher: Matcher, state: T_State, url: Message = Arg()):
    if text := re_docs(str(url)):
        nwe = NotWriteExcel(state["user"])
        if nwe.is_student:
            user: Student = state["user"]
            await nwe.not_write_excel(text, user.class_table)


# --------------------------------- 水印 ---------------------------------
@add_watermark.handle()
async def _(matcher: Matcher, msg: Message = CommandArg(), _: Student = STUDENT):
    if images := msg.get("image"):
        matcher.set_arg("images", images)


@add_watermark.got("images", prompt="图片发给我吧")
async def _(matcher: Matcher, state: T_State, images: Message = Arg()):
    if images := images.get("image"):
        w = Watermark(state["student"])
        await matcher.finish(
            Message(
                [
                    MessageSegment.image(image)
                    async for image in w.watermark(extract_image_urls(images))
                ]
            )
        )
    await matcher.finish("不发算了")
