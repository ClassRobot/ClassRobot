from abc import ABC, abstractmethod
from asgiref.sync import sync_to_async
from imgkit import from_string
from utils.tools.templates import create_template_env

options = {
    'width': 600,
    'encoding': 'UTF-8',
}

env = create_template_env("helper")


class BaseHelper(ABC):
    @abstractmethod
    async def to_string(self) -> str: ...

    async def to_image(self) -> bytes: 
        return await sync_to_async(from_string)(
            await self.to_string(), None, options=options)
