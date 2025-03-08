from time import time

from .schema import Messages
from .typings import ChatCompletionToolParam

chat_sessions: dict[str, "ChatSession"] = {}
session_timeout = 60 * 60 * 24  # 24小时


class ChatSession:
    functools: list[ChatCompletionToolParam] | None = None

    def __init__(self, session_id: str) -> None:
        self.messages = Messages()
        self.update_time: float = time()
        self.session_id: str = session_id
        self.is_new = False
        """是否为新的session"""

    @property
    def is_timeout(self) -> bool:
        return time() - self.update_time > session_timeout

    def __new__(cls, session_id: str) -> "ChatSession":
        # 检查是否有过期的session
        if session_id in chat_sessions and chat_sessions[session_id].is_timeout:
            del chat_sessions[session_id]

        if session_id not in chat_sessions:
            chat_sessions[session_id] = super().__new__(cls)
            chat_sessions[session_id].is_new = True
            return chat_sessions[session_id]

        chat_sessions[session_id].update_time = time()
        return chat_sessions[session_id]

    def dict(self):
        return self.messages.dict(include={"messages"})
