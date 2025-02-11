from typing import Annotated

from nonebot.params import Depends
from utils.llm import client_create
from utils.llm.schema import Messages
from nonebot_plugin_alconna import UniMessage
from utils.models.annotated import UserOrCreatedDepends
from utils.llm.util import json_loads, uni_message_to_contents

from .prompt import get_prompt_system
from .exception import SessionLockError
from .schemas import ChatMessage, AutoTaskList


class ChatSession:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.lock = False  # 聊天锁，防止一轮聊天还没结束又开始新的聊天
        self.messages = Messages()
        self.messages.system_message(content=get_prompt_system())

    async def send_message(self, message: str | UniMessage | ChatMessage):
        if self.lock:
            raise SessionLockError("聊天锁已经被锁定，无法发送消息！")
        try:
            self.lock = True
            self.messages.user_message(
                message.message
                if isinstance(message, ChatMessage)
                else uni_message_to_contents(message)
            )
            response = await client_create(self.messages)
            # 可能会存在```json和```这种情况，需要删除
            content = response.choices[0].message.content  # type: ignore
            if content:
                print(content)
                auto_tasks = AutoTaskList.parse_obj(json_loads(content))

                if auto_tasks.is_violation:
                    auto_tasks.reply = "用户发送的消息包含违规内容，已被屏蔽！"

                if auto_tasks.reply:
                    self.messages.assistant_message(
                        auto_tasks.json(ensure_ascii=False),
                        priority=auto_tasks.priority,
                    )
                return auto_tasks
            return content
        finally:
            self.lock = False


class ChatSessionManager:
    def __init__(self):
        self.sessions: dict[int, ChatSession] = {}

    def get_chat_session(self, user_id: int):
        if session := self.sessions.get(user_id):
            return session
        session = ChatSession(user_id)
        self.sessions[user_id] = session
        return session


async def get_chat_session(user: UserOrCreatedDepends) -> ChatSession:
    return chat_session_manager.get_chat_session(user.id)


ChatSessionDepends = Annotated[ChatSession, Depends(get_chat_session)]
chat_session_manager = ChatSessionManager()
