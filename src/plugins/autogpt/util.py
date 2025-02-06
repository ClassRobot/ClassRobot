import json
from typing import Annotated

from nonebot.params import Depends
from utils.AutoGPT import client_create
from nonebot_plugin_alconna import UniMessage
from utils.models.annotated import UserOrCreatedDepends
from utils.AutoGPT.schema import Role, Context, Messages

from .prompt import get_prompt_system
from .schemas import ChatMessage, AutoTaskList


class ChatSession:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.messages = Messages(
            messages=[Context(role=Role.system, content=get_prompt_system())]
        )

    async def send_message(self, message: str | UniMessage):
        self.messages.user_message(ChatMessage(user_id=self.user_id).extend(message))
        response = await client_create(self.messages)
        # 可能会存在```json和```这种情况，需要删除
        content = response.choices[0].message.content  # type: ignore
        if content:
            contents = content.split("\n")
            start, end = 0, len(contents)
            for i, v in enumerate(contents):
                if v.startswith("```json"):
                    start = i + 1
                if v.endswith("```"):
                    end = i
            print(content)
            content = "\n".join(contents[start:end]).strip()
            auto_tasks = AutoTaskList.parse_obj(json.loads(content))

            if auto_tasks.is_violation:
                auto_tasks.reply = "用户发送的消息包含违规内容，已被屏蔽！"

            if auto_tasks.reply:
                self.messages.assistant_message(
                    auto_tasks.json(ensure_ascii=False), priority=auto_tasks.priority
                )
            return auto_tasks
        return content


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


chat_session_manager = ChatSessionManager()
ChatSessionDepends = Annotated[ChatSession, Depends(get_chat_session)]
