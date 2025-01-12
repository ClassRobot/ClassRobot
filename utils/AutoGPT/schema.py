from pydantic import BaseModel
from strenum import StrEnum


class Role(StrEnum):
    user = "user"
    system = "system"
    assistant = "assistant"


class Context(BaseModel):
    role: Role
    content: str


class Messages(BaseModel):
    messages: list[Context]
    
    def add_message(self, role: Role, content: str):
        self.messages.append(Context(role=role, content=content))

    def user_message(self, content: str):
        self.add_message(role=Role.user, content=content)

    def system_message(self, content: str):
        self.add_message(role=Role.system, content=content)

    def assistant_message(self, content: str):
        self.add_message(role=Role.assistant, content=content)
