import json
from datetime import datetime
from typing import Callable, Iterator, Awaitable

from nonebot import logger
from pydantic import BaseModel
from src.core.llm.message import Content
from nonebot_plugin_apscheduler import scheduler
from apscheduler.jobstores.base import JobLookupError
from src.models import User, Group, ScheduledNotice


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
    """描述通知消息的数据结构。"""
    id: int | None = None
    "通知事件"
    title: str
    "通知标题"
    notice_time: datetime | None = None
    "通知时间,如果为None则表示立即通知,如果无法理解用户说的是什么时候通知,则默认为立即通知"
    recipients: list[NoticeGroup | NoticePrivate]
    "通知对象"
    messages: list[Content] = []
    "通知内容"

    async def create(self, user: User) -> ScheduledNotice:
        """创建当前数据。

        参数:
            user (User): 当前用户对象。

        返回:
            ScheduledNotice: 返回处理结果。
        """
        self_dict = self.dict()
        sn = await ScheduledNotice(
            title=self.title,
            notice_time=self.notice_time,
            recipients=json.dumps(self_dict["recipients"]),
            messages=json.dumps(self_dict["messages"]),
            creator=user,
        ).create()
        self.id = sn.id
        logger.success(f"create notice {sn.id} | {self.title}")
        return sn

    async def get_notice_users(self) -> list[User]:
        """获取通知用户。"""
        users: list[User] = []
        if not self.recipients:
            return users
        for recipient in self.recipients:
            if isinstance(recipient, NoticePrivate) and (user := await User.filter(id=recipient.user_id).first()):
                users.append(user)
        return users

    async def get_notice_groups(self) -> list[Group]:
        """获取通知群组。"""
        groups: list[Group] = []
        if not self.recipients:
            return groups
        for recipient in self.recipients:
            if isinstance(recipient, NoticeGroup) and (group := await Group.filter(id=recipient.group_id).first()):
                groups.append(group)
        return groups

    async def get_creator(self) -> User | None:
        """获取creator。"""
        if not self.id:
            raise ValueError("通知id不能为空,需要先调用create保存置数据库后获取ID")
        if sn := await ScheduledNotice.filter(id=self.id).first():
            return sn.creator

    @property
    def is_immediate(self) -> bool:
        """判断通知是否立即发送"""
        return self.notice_time is None or self.notice_time.timestamp() <= datetime.now().timestamp()

    @classmethod
    def loads(cls, notice: ScheduledNotice):
        """处理加载相关逻辑。

        参数:
            notice (ScheduledNotice): 通知对象。
        """
        return cls(
            id=notice.id,
            title=notice.title,
            notice_time=notice.notice_time,
            recipients=json.loads(notice.recipients),
            messages=json.loads(notice.messages),
        )

    def add_job(self, func: Callable[["Notice"], Awaitable[None]]):
        """添加定时任务

        参数:
            func (Callable[['Notice'], Awaitable[None]]): func。
        """
        if self.is_immediate:  # 如果是立即发送的任务则不创建
            return
        elif self.id is None:
            raise ValueError("通知id不能为空,需要先调用create保存置数据库后获取ID")
        scheduler.add_job(
            func,
            id=f"notice_{self.id}",
            run_date=self.notice_time,
            args=[self],
        )
        logger.success(f"add job notice_{self.id} | {self.title}")

    async def remove_job(self):
        """移除定时任务"""
        if self.id is not None:
            logger.info(f"remove job notice_{self.id} | {self.title}")
            await ScheduledNotice.filter(id=self.id).delete()
            try:
                scheduler.remove_job(f"notice_{self.id}")
            except JobLookupError:
                logger.warning("Notice")


class Notices(BaseModel):
    "通知列表"
    notices: list[Notice] = []
    "通知列表"
    reply: str
    "回复给用户的消息，如果`notices`里面有任务的话则告知用户机器人接下来会帮助用户做什么"
    is_invalid: bool = False
    "用户的通知内容是否无效或胡言乱语或者找不到通知对象则为True"

    async def create_all(self, user: User):
        """创建相关内容。

        参数:
            user (User): 当前用户对象。
        """
        for notice in self.notices:
            if not notice.is_immediate:
                await notice.create(user)

    def __iter__(self) -> Iterator[Notice]:
        """返回迭代器。"""
        return self.notices.__iter__()

    def remove(self, notice: Notice):
        """移除指定内容。

        参数:
            notice (Notice): 通知对象。
        """
        self.notices.remove(notice)
