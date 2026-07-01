from __future__ import annotations

from typing import Any
from itertools import count
from dataclasses import field, dataclass

import pytest
import pytest_asyncio
from nonebot.adapters.onebot.v11 import Bot as OneBot11Bot
from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot.adapters.onebot.v11.event import Sender, GroupMessageEvent, PrivateMessageEvent

PLATFORM_ID = "onebot11.qq_client"
PLATFORM_NAME = ""
MESSAGE_ID_COUNTER = count(1)


class MessageText:
    """用于 nonebug 断言的宽松文本匹配器。"""

    def __init__(self, *parts: str, absent: tuple[str, ...] = ()):
        self.parts = tuple(part for part in parts if part)
        self.absent = tuple(part for part in absent if part)

    @staticmethod
    def _to_text(message: Any) -> str:
        if hasattr(message, "extract_plain_text"):
            return message.extract_plain_text()
        return str(message)

    def __eq__(self, other: Any) -> bool:
        text = self._to_text(other)
        return all(part in text for part in self.parts) and all(part not in text for part in self.absent)

    def __repr__(self) -> str:
        return f"MessageText(parts={self.parts!r}, absent={self.absent!r})"


@dataclass(slots=True)
class SendCall:
    """记录一次 matcher 的真实发送内容。"""

    bot: Any
    event: Any
    message: Any
    kwargs: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return MessageText._to_text(self.message)


class SendRecorder:
    """通过覆盖 `ctx.got_call_send` 录制 nonebug fake bot 的发送调用。"""

    def __init__(self):
        self.calls: list[SendCall] = []

    def bind(self, ctx) -> SendRecorder:
        def capture_send(bot, event, message, **kwargs):
            self.calls.append(SendCall(bot=bot, event=event, message=message, kwargs=kwargs))
            return None

        ctx.got_call_send = capture_send  # type: ignore[method-assign]
        return self

    def assert_any(self, *parts: str, absent: tuple[str, ...] = ()) -> None:
        matcher = MessageText(*parts, absent=absent)
        assert any(matcher == call.message for call in self.calls), (
            f"未找到匹配发送消息: {matcher!r}\n" f"实际发送内容: {[call.text for call in self.calls]!r}"
        )


class MemoryCache:
    """简易内存缓存，用于替代 Redis。"""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def set(self, key: str, value: Any, ex: int = 0):
        self.store[str(key)] = str(value)

    async def get(self, key: str):
        return self.store.get(str(key))

    async def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            deleted += int(self.store.pop(str(key), None) is not None)
        return deleted


class OneBotFactory:
    """构造 nonebug 所需的 OneBot V11 bot 与消息事件。"""

    @staticmethod
    def _resolve_message_id(message_id: int | None) -> int:
        """为测试事件生成全局唯一的消息 ID，避免被平台层当作重复消息忽略。"""
        sequence = next(MESSAGE_ID_COUNTER)
        if message_id is None:
            return sequence
        return sequence * 1000 + message_id

    @staticmethod
    def create_bot(ctx, *, self_id: str = "114514"):
        adapter = ctx.create_adapter(base=OneBot11Adapter)
        # nonebug 的 fake adapter 默认名称是 "fake"，会导致 nonebot-plugin-alconna
        # 把当前事件识别成 nonebug 平台，从而无法正确构造 OneBot11 的 MsgTarget / EventSession。
        # 这里把适配器名称恢复成真实的 OneBot V11，既保留 nonebug 的发送拦截能力，
        # 也让命令依赖中的平台解析与生产环境保持一致。
        adapter.__class__.get_name = classmethod(lambda cls: OneBot11Adapter.get_name())  # type: ignore[method-assign]
        return ctx.create_bot(base=OneBot11Bot, adapter=adapter, self_id=str(self_id), auto_connect=False)

    @staticmethod
    def message(content: str | Message | list[MessageSegment]) -> Message:
        if isinstance(content, Message):
            return content.copy()
        return Message(content)

    @staticmethod
    def file_command(
        command: str,
        *,
        file_name: str = "students.xlsx",
        url: str = "https://example.invalid/students.xlsx",
        file_id: str = "file-1",
    ) -> Message:
        return Message(
            [
                MessageSegment.text(command),
                MessageSegment("file", {"file_name": file_name, "url": url, "file_id": file_id}),
            ]
        )

    @staticmethod
    def _sender(user_id: int, nickname: str | None = None, role: str = "member") -> Sender:
        nick = nickname or f"user-{user_id}"
        return Sender(user_id=user_id, nickname=nick, card=nick, role=role)

    def private_event(
        self,
        content: str | Message | list[MessageSegment],
        *,
        user_id: int,
        message_id: int | None = None,
        self_id: int = 114514,
        nickname: str | None = None,
    ) -> PrivateMessageEvent:
        resolved_message_id = self._resolve_message_id(message_id)
        message = self.message(content)
        return PrivateMessageEvent(
            time=resolved_message_id,
            self_id=self_id,
            post_type="message",
            sub_type="friend",
            user_id=user_id,
            message_type="private",
            message_id=resolved_message_id,
            message=message,
            original_message=message.copy(),
            raw_message=str(message),
            font=0,
            sender=self._sender(user_id, nickname),
        )

    def group_event(
        self,
        content: str | Message | list[MessageSegment],
        *,
        user_id: int,
        group_id: int,
        message_id: int | None = None,
        self_id: int = 114514,
        nickname: str | None = None,
        role: str = "member",
    ) -> GroupMessageEvent:
        resolved_message_id = self._resolve_message_id(message_id)
        message = self.message(content)
        return GroupMessageEvent(
            time=resolved_message_id,
            self_id=self_id,
            post_type="message",
            sub_type="normal",
            user_id=user_id,
            message_type="group",
            message_id=resolved_message_id,
            message=message,
            original_message=message.copy(),
            raw_message=str(message),
            font=0,
            sender=self._sender(user_id, nickname, role),
            group_id=group_id,
        )


class CommandModelFactory:
    """通过项目自身模型方法搭建测试业务数据。"""

    async def create_user(self, *, account_id: int, nickname: str | None = None, is_admin: bool = False):
        from src.models import User, UserBind

        nickname = nickname or f"user-{account_id}"
        user = await User.create_user(nickname=nickname, username=f"user_{account_id}")
        if is_admin:
            user = await user.update(is_admin=True)
        await UserBind.bind_user(PLATFORM_ID, str(account_id), user)
        return await User.filter(id=user.id).first()

    async def create_school(self, name: str = "测试大学"):
        from src.models import School

        return await School(name=name).create()

    async def create_college(self, school, name: str = "计算机学院"):
        from src.models import College

        return await College(name=name, school_id=school.id).create()

    async def create_major(self, school, college, name: str = "软件工程"):
        from src.models import Major

        return await Major(name=name, school_id=school.id, college_id=college.id).create()

    async def create_teacher(self, user, *, name: str | None = None, school=None, college=None):
        from src.models import Teacher

        teacher = await Teacher.create_teacher(
            name or user.nickname,
            user,
            school_id=school.id if school else None,
            college_id=college.id if college else None,
        )
        return await Teacher.filter(id=teacher.id).first()

    async def create_classes(
        self,
        *,
        name: str,
        owner,
        group_id: int,
        teacher=None,
        school=None,
        college=None,
        major=None,
    ):
        from src.models import Classes
        from src.core.auth import TeacherClassesRole

        classes = await Classes.create_classes(
            name,
            platform_name=PLATFORM_NAME,
            platform_id=PLATFORM_ID,
            channel_id=str(group_id),
            guild_id=None,
            user=owner,
            school_id=school.id if school else None,
            college_id=college.id if college else None,
            major=major.name if major else None,
            major_id=major.id if major else None,
        )
        if teacher is not None:
            await classes.bind_teacher(teacher)
            await classes.update_teacher_role(teacher, TeacherClassesRole.counselor)
        return await Classes.filter(id=classes.id).first()

    async def create_student(self, user, *, classes, name: str | None = None, school=None):
        from src.models import Student

        student = await Student.create_student(
            name or user.nickname,
            classes,
            user,
            school_id=school.id if school else classes.school_id,
        )
        return await Student.filter(id=student.id).first()


async def _recreate_orm_schema() -> None:
    import nonebot_plugin_orm as orm

    if not hasattr(orm, "_metadatas") or not getattr(orm, "_metadatas", None):
        orm._init_orm()
    if hasattr(orm, "_scoped_sessions"):
        await orm._scoped_sessions.remove()
    for bind_name, metadata in orm._metadatas.items():
        engine = orm._engines[bind_name]
        async with engine.begin() as connection:
            # 始终在同一个临时测试库内 drop/create，
            # 让 startup 同步、metadata 与后续命令测试保持一致。
            await connection.run_sync(metadata.drop_all)
            await connection.run_sync(metadata.create_all)


@pytest.fixture(scope="session", autouse=True)
def helper_runtime(loaded_plugins):
    """在命令交互测试前初始化帮助目录和统一鉴权。"""

    from src.platform.helper.runtime import bootstrap_helper_runtime

    bootstrap_helper_runtime(loaded_plugins)
    return loaded_plugins


@pytest_asyncio.fixture(scope="session", autouse=True)
async def command_orm(loaded_plugins):
    """初始化命令交互测试所需的 ORM，并在会话结束时回收连接。"""

    await _recreate_orm_schema()
    yield

    import nonebot_plugin_orm as orm

    for engine in orm._engines.values():
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def reset_command_orm(command_orm):
    """按测试重建表结构，保证命令交互场景相互隔离。"""

    await _recreate_orm_schema()
    yield


@pytest.fixture
def onebot() -> OneBotFactory:
    return OneBotFactory()


@pytest.fixture
def contains():
    return MessageText


@pytest.fixture
def send_recorder():
    def _factory(ctx) -> SendRecorder:
        return SendRecorder().bind(ctx)

    return _factory


@pytest_asyncio.fixture
async def models() -> CommandModelFactory:
    return CommandModelFactory()


@pytest.fixture(autouse=True)
def patch_onebot_userinfo(monkeypatch, loaded_plugins):
    """避免 nonebug 场景中为昵称解析额外声明 OneBot API 调用。"""

    from nonebot_plugin_userinfo.adapters.onebot_v11 import Getter, QQAvatar, UserInfo, _sex_to_gender

    async def fake_get_info(self, user_id: str):
        sender = getattr(self.event, "sender", None)
        nickname = None
        sex = None
        if sender is not None:
            nickname = getattr(sender, "card", None) or getattr(sender, "nickname", None)
            sex = getattr(sender, "sex", None)
        qq = int(user_id)
        return UserInfo(
            user_id=str(user_id),
            user_name=nickname or f"user-{user_id}",
            user_displayname=nickname,
            user_avatar=QQAvatar(qq=qq),
            user_gender=_sex_to_gender(sex),
        )

    monkeypatch.setattr(Getter, "_get_info", fake_get_info)


@pytest.fixture
def fake_cache(monkeypatch) -> MemoryCache:
    """把命令里的缓存调用切到内存实现。"""

    import src.core.cache as cache_module
    import src.plugins.application.active.user as user_module

    cache = MemoryCache()
    monkeypatch.setattr(cache_module, "get_cache", lambda db=0, decode_responses=True: cache)
    monkeypatch.setattr(user_module, "get_cache", lambda: cache)
    return cache
