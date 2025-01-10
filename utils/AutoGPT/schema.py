from pydantic import BaseModel
from strenum import StrEnum


class Rote(StrEnum):
    user = "user"
    system = "system"
    assistant = "assistant"


class Context(BaseModel):
    rote: Rote
    content: str
