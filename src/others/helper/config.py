"""
Author: Melodyknit 2711402357@qq.com
Date: 2023-02-11 20:06:30
LastEditors: Melodyknit 2711402357@qq.com
LastEditTime: 2023-05-25 20:33:43
FilePath: classbot\src\others\helper\config.py
Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
"""
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
