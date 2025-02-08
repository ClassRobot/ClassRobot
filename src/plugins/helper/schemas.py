from strenum import StrEnum
from nonebot.log import logger
from pydantic import BaseModel, validator


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
    description: str
    tags: set[str] = set()
    params: list[Param] = []
    aliases: set[str] = set()
    example: list[Context] | str = []

    def __init__(
        self,
        command: str,
        description: str,
        tags: set[str] = set(),
        params: list[Param] = [],
        aliases: set[str] = set(),
        example: list[Context] | str = [],
    ):
        """帮助信息

        Args:
            command (str): 命令名称
            description (str): 命令描述
            params (list[Param], optional): 命令参数. Defaults to [].
            tags (set[str], optional): 命令标签. Defaults to set().
            aliases (set[str], optional): 命令别名. Defaults to set().
            example (list[Context] | str, optional): 使用例子. Defaults to [].
        """
        aliases |= {command}
        super().__init__(
            command=command,
            description=description,
            params=params,
            tags=tags,
            aliases=aliases,
            example=example,
        )
        helper_menu.add_helper(self)

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
            f"示例 | \n{self.example_text() or '无'}"
        )

    def overview(self) -> str:
        """简要概述"""
        return (
            f"命令 | {self.command}\n"
            f"参数 | {', '.join(map(str, self.params)) or '无'}\n"
            f"别名 | {', '.join(self.aliases) or '无'}\n"
            f"描述 | {self.description}\n"
        )

    def example_text(self) -> str:
        if isinstance(self.example, str):
            return self.example
        return "\n".join(map(str, self.example))


class HelperMenu:
    def __init__(self, *helpers: Helper):
        self.helper_search: dict[str, Helper] = {}
        self.helpers: list[Helper] = []
        self.add_helper(*helpers)

    def to_string(self):
        return "\n".join(helper.overview() for helper in self.helpers)

    def add_helper(self, *helpers: Helper):
        for helper in helpers:
            if helper not in self.helpers:
                self.helpers.append(helper)
            for cmd in helper.aliases | {helper.command}:
                if cmd in self.helper_search:
                    logger.warning(f"命令 {cmd} 已存在，将被覆盖")
                self.helper_search[cmd] = helper

    def get_helper(self, command: str) -> Helper | None:
        return self.helper_search.get(command)


helper_menu = HelperMenu()
