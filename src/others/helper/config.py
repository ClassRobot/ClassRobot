from abc import ABC, abstractmethod
from utils.tools import html_to_image
from utils.tools.templates import create_template_env


env = create_template_env("helper")


class BaseHelper(ABC):
    @abstractmethod
    async def to_string(self) -> str:
        ...

    async def to_image(self) -> bytes:
        return await html_to_image(await self.to_string())
