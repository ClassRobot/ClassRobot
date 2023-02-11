from nonebot import on_command
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.params import CommandArg, Arg
from nonebot.matcher import Matcher

from .methods import PushFeedback, ShowFeedback

push_feedback = on_command("反馈", priority=10, block=True)
show_feedback = on_command('查看反馈', aliases={"查询反馈"}, priority=10, block=True)


@push_feedback.handle()
async def _(matcher: Matcher, state: T_State, msg: Message = CommandArg()):
    feedback = PushFeedback()
    state["feedback"] = feedback
    feedback.save_file.add_file(msg)
    if text := msg.get("text"):
        matcher.set_arg("context", text)


@push_feedback.got("context", prompt="想反馈一些什么呢？")
async def _(matcher: Matcher, event: MessageEvent, state: T_State, context: Message = Arg()):
    feedback: PushFeedback = state["feedback"]
    feedback.save_file.add_file(context)
    if text := context.extract_plain_text().strip():
        if feedback.save_file.file_exists:
            await feedback.push_feedback(text, event.user_id)
            await matcher.finish("感谢您的反馈！")
    else:
        await matcher.finish("不说话就算了！")


@push_feedback.got("images", prompt="你还可以提供一些截图")
async def _(
    state: T_State, 
    matcher: Matcher, 
    event: MessageEvent, 
    images: Message = Arg(), 
    context: Message = Arg("context")
):
    feedback: PushFeedback = state["feedback"]
    feedback.save_file.add_file(images)
    await feedback.push_feedback(context.extract_plain_text().strip(), event.user_id)
    await matcher.finish("感谢您的反馈！")


# --------------------------------- 查看反馈 ---------------------------------
@show_feedback.handle()
async def _(matcher: Matcher, msg: Message = CommandArg()):
    feedback = ShowFeedback()
    if image := await feedback.show_feedback(msg.extract_plain_text().strip()):
        await matcher.finish(MessageSegment.image(image))
    await matcher.finish("没有" + msg)


__helper__ = [{
    "cmd": "反馈",
    "alias": ["意见", "建议"],
    "params": ["内容", "截图"],
    "tags": ["意见", "建议"],
    "use": [["反馈 机器人的xxx功能存在bug [截图]", "感谢您的反馈！"]],
    "doc": "所有人都可以向机器人提供反馈内容，您对机器人功能的任何意见和建议会让机器人越来越好。"
}, {
    "cmd": "查询反馈",
    "alias": ["查看反馈"],
    "params": ["日期或者反馈ID（也可以不写）"],
    "tags": ["意见", "建议"]
}]


