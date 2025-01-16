import json
from pprint import pprint

from utils.AutoGPT import client_create
from utils.AutoGPT.schema import Role, Context, Messages

from .schemas import AutoTaskList
from .prompt import get_prompt_system


class ChatSession:
    def __init__(self) -> None:
        self.messages = Messages(
            messages=[Context(role=Role.system, content=get_prompt_system())]
        )

    async def send_message(self, message: str):
        self.messages.user_message(message)
        response = await client_create(**self.messages.dict())
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
            content = "\n".join(contents[start:end]).strip()
            print(content)
            auto_tasks = AutoTaskList.parse_obj(json.loads(content))
            if auto_tasks.reply:
                self.messages.assistant_message(auto_tasks.json(ensure_ascii=False))
            pprint(self.messages.dict())
            return auto_tasks
        return content


class ChatSessionManager:
    def __init__(self):
        self.sessions: dict[int, ChatSession] = {}

    def get_chat_session(self, user_id: int):
        if session := self.sessions.get(user_id):
            return session
        session = ChatSession()
        self.sessions[user_id] = session
        return session


chat_session_manager = ChatSessionManager()
