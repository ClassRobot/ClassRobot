from typing import Iterable, Generator

from nonebot import logger
from strenum import StrEnum
from utils.roles import UserRole
from utils.config import template_dir
from pydantic import BaseModel, validator
from nonebot_plugin_htmlrender import template_to_pic


class ParamMode(StrEnum):
    OPTIONAL = "?"
    """可选参数"""
    ONE_OR_MORE = "+"
    """至少一个参数"""
    ZERO_OR_MORE = "*"
    """零个或多个参数"""


class Context(BaseModel):
    """example 中的命令使用上下文"""

    rote: str
    content: str

    def __str__(self) -> str:
        return f"{self.rote}:\n\t{self.content}"


class Param(BaseModel):
    """命令参数"""

    name: str
    description: str | None = None
    mode: ParamMode | None = None

    @validator("name")
    def name_validator(cls, value: str) -> str:
        if not value:
            raise ValueError("参数名不能为空")
        # name不能存在mode中的字符
        if any(mode in value for mode in ParamMode):
            raise ValueError("参数名不能包含特殊字符")
        return value

    def __str__(self) -> str:
        return self.name + (self.mode or "")


class Helper(BaseModel):
    """命令帮助信息"""

    command: str
    """命令名称"""
    description: str
    """命令描述"""
    tags: set[str] = set()
    """命令标签"""
    roles: set[UserRole] = set()
    """命令权限"""
    params: list[Param] = []
    """命令参数"""
    aliases: set[str] = set()
    """命令别名"""
    example: list[Context] = []
    """使用例子"""

    @property
    def commands(self) -> set[str]:
        """command + aliases"""
        return {self.command, *self.aliases}

    @property
    def example_text(self) -> str:
        if isinstance(self.example, str):
            return self.example
        return "\n\n".join(map(str, self.example))

    def is_command(self, command: str) -> bool:
        """查看是否为指定命令

        Args:
            command (str): 命令名称或别名

        Returns:
            bool: 是否为指定命令
        """
        command = command.strip()
        return command == self.command or command in self.aliases

    def to_string(self) -> str:
        """详细描述"""
        return (
            f"命令 | {self.command}\n"
            f"参数 | {', '.join(map(str, self.params)) or '无'}\n"
            f"别名 | {', '.join(self.aliases) or '无'}\n"
            f"描述 | {self.description}\n"
            f"示例 | \n{self.example_text or '无'}"
        )

    def overview(self) -> str:
        """简要概述"""
        return (
            f"命令 | {self.command}\n"
            f"参数 | {', '.join(map(str, self.params)) or '无'}\n"
            f"别名 | {', '.join(self.aliases) or '无'}\n"
            f"描述 | {self.description}\n"
        )


class Helpers(BaseModel):
    helpers: list[Helper] = []
    helper_search: dict[str, Helper] = {}

    def get_helper(self, command: str) -> Helper | None:
        return self.helper_search.get(command)

    def get_tags_helpers(self, *tags: str) -> "Helpers":
        """包含tag的helper"""
        helpers = Helpers()
        helpers.extend(
            helper
            for helper in self.helpers
            if not helper or helper.tags.intersection(tags)
        )
        return helpers

    def get_roles_helpers(self, *roles: UserRole) -> "Helpers":
        """包含role的helper"""
        helpers = Helpers()
        helpers.extend(
            helper
            for helper in self.helpers
            if not helper.roles or helper.roles.intersection(roles)
        )
        return helpers

    def extend(self, helpers: Iterable[Helper]):
        for helper in helpers:
            self.append(helper)

    def append(self, helper: Helper):
        helper.aliases |= {helper.command}
        if not helper.example:
            helper.example = [
                Context(
                    rote=UserRole.user,
                    content=" ".join(
                        (helper.command, *(p.name for p in helper.params))
                    ),
                )
            ]
        if helper in self.helpers:
            logger.warning(f"helper {helper.command} already exists")
        else:
            self.helpers.append(helper)
        for command in helper.commands:
            if command in self.helper_search:
                # 命令别名重复
                logger.warning(f"command {command} already exists")
            else:
                self.helper_search[command] = helper

    def __iter__(self) -> Generator[Helper, None, None]:
        yield from self.helpers

    async def render_pic(self) -> bytes:
        html = await template_to_pic(
            str(template_dir),
            "helper.html",
            {
                "helpers": self.helpers,
            },
        )
        return html

    def to_string(self):
        return "\n".join(helper.overview() for helper in self.helpers)
