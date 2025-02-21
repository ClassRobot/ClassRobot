from time import time
from typing import Annotated

from utils.helper import Helpers
from nonebot.params import Depends
from utils.llm import client_create
from utils.llm.schema import Messages
from nonebot_plugin_alconna import UniMessage
from utils.helper.depends import HelpersDepends
from utils.models.depends import UserOrCreatedDepends
from utils.llm.util import json_loads, uni_message_to_contents

from .prompt import get_prompt_system
from .exception import SessionLockError
from .schemas import ChatMessage, AutoTaskList


class ChatSession:
    def __init__(self, user_id: int, helpers: Helpers) -> None:
        self.update_time = time()
        self.user_id = user_id
        self.lock = False  # 聊天锁，防止一轮聊天还没结束又开始新的聊天
        self.messages = Messages()
        self.messages.system_message(get_prompt_system(helpers))

    def update_helpers(self, helpers: Helpers):
        self.messages[0].content = get_prompt_system(helpers)

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
                    )
                return auto_tasks
            return content
        finally:
            self.lock = False


class ChatSessionManager:
    timeout = 60 * 60 * 24  # 24小时

    def __init__(self):
        self.sessions: dict[int, ChatSession] = {}

    # 检查是否有过期的session然后删除
    def check_timeout(self):
        current_time = time()
        for session in self.sessions.values():
            if current_time - session.update_time > self.timeout:
                del self.sessions[session.user_id]

    def get_chat_session(self, user_id: int, helpers: Helpers) -> ChatSession:
        # 检查是否有过期的session
        self.check_timeout()

        if session := self.sessions.get(user_id):
            session.update_time = time()
            return session
        session = ChatSession(user_id, helpers)
        self.sessions[user_id] = session
        return session


async def get_chat_session(
    user: UserOrCreatedDepends, helpers: HelpersDepends
) -> ChatSession:
    chat_session = chat_session_manager.get_chat_session(user.id, helpers)
    chat_session.update_helpers(helpers)
    return chat_session


ChatSessionDepends = Annotated[ChatSession, Depends(get_chat_session)]
chat_session_manager = ChatSessionManager()
