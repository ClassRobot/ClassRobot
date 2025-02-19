from datetime import datetime

from utils.llm.schema import Content
from utils.llm.util import json_loads
from utils.models import User, Student
from nonebot_plugin_alconna import Image
from utils.llm import Messages, client_create

from .schemes import Leave
from .prompt import plugin_prompt


class BaseLeave:
    def __init__(self, user: User) -> None:
        self.user = user


class AddLeave:
    def __init__(self, student: Student) -> None:
        self.student = student
        self.messages = Messages()
        self.messages.system_message(plugin_prompt + self.current_state)

    @property
    def current_state(self):
        return f"\n当前时间: {datetime.now()}"

    async def send_message(self, messages: list[str | Image]) -> Leave | None:
        self.messages.user_message(
            [
                (
                    Content(type="text", value=msg)
                    if isinstance(msg, str)
                    else Content(type="image", value=msg.url)  # type: ignore
                )
                for msg in messages
            ]
        )
        chat = await client_create(messages=self.messages)
        if chat.choices[0].message.content:
            print(chat.choices[0].message.content)
            data = Leave.parse_obj(json_loads(chat.choices[0].message.content))
            return data
