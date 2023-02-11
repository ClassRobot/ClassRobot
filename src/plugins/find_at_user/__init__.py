from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.matcher import Matcher

from utils.manages import CLASS_TABLE, USER, User
from utils.orm import ClassTable

from .commands import find_user, at_user
from .methods import FindAtUser, FindUser


# --------------------------------- 查询用户 ---------------------------------
@find_user.handle()
async def _(matcher: Matcher, msg: Message = CommandArg(), class_table: ClassTable = CLASS_TABLE, user: User = USER):
    text = msg.extract_plain_text() or str(user.qq)
    find = FindUser(text)
    if text := await find.find_user(class_table):
        await matcher.finish(text)
    await matcher.finish("没有找到！")


# --------------------------------- at群内的用户 ---------------------------------
@at_user.handle()
async def _(matcher: Matcher, msg: Message = CommandArg(), class_table: ClassTable = CLASS_TABLE, _: User = USER):
    if text := msg.extract_plain_text():
        find = FindAtUser(text)
        if users := await find.find_at_user(class_table):
            await matcher.finish(Message(MessageSegment.at(qq) for qq in users))
        await matcher.finish("没有找到你需要at的人")
