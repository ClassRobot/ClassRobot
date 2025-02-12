from datetime import datetime

from pydantic import BaseModel
from utils.llm.schema import Content


class NoticeGroup(BaseModel):
    "通知的群"
    group_id: int
    "通知的群ID"
    at_all: bool = False
    "是否@所有人"
    at_user: list[int] = []
    "需要@的用户"


class NoticePrivate(BaseModel):
    "通知的私聊用户"
    user_id: int
    "通知的用户ID"


class Notice(BaseModel):
    "通知事件"
    title: str
    "通知标题"
    notice_time: datetime | None = None
    "通知时间,如果为None则表示立即通知"
    recipients: list[NoticeGroup | NoticePrivate] | None = None
    "通知对象,如果为None则是关于自己的通知事件,类似于定时什么时候提前自己起床这种任务"
    messages: list[Content] = []
    "通知内容"


class Notices(BaseModel):
    "通知列表"
    notices: list[Notice] = []
    "通知列表"
    reply: str | None = None
    "回复给用户的消息，如果`notices`里面有任务的话则告知用户机器人接下来会帮助用户做什么"
    is_invalid: bool = False
    "用户的通知内容是否无效或胡言乱语或者找不到通知对象则为True"
