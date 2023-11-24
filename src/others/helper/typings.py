from typing import Literal

from pydantic import BaseModel
from utils.typings import UserType


class ExampleMessage(BaseModel):
    user_type: Literal["bot"] | UserType
    message: str

    def __repr__(self) -> str:
        return f"[{str(self.user_type)}]: {self.message}"

    def __str__(self) -> str:
        return self.__repr__()


class Helper(BaseModel):
    command: str  # 命令名称
    description: str  # 命令说明
    usage: str  # 使用方式
    example: list[ExampleMessage]  # 使用示例
    category: set[str]  # 命令类别
    allowed_user_types: set[UserType] | None = None  # 允许使用的用户类型
    aliases: set[str] = set()  # 命令别名

    def to_string(self) -> str:
        return """# {command}

{description}

**使用方式:**
`{usage}`

**使用示例:**
{example}

**插件类别:**
{category}

**插件别名:**
{aliases}""".format(
            command=self.command,
            description=self.description,
            usage=self.usage,
            example="\n".join(f"- {i}" for i in self.example),
            category=", ".join(f"`{i}`" for i in self.category),
            aliases=", ".join(f"`{i}`" for i in self.aliases),
        )


class HelperCategory(BaseModel):
    category: str  # 类别名称
    commands: list[Helper] = []  # 类别下的命令

    def add(self, helper: Helper):
        self.commands.append(helper)

    def to_string(self) -> str:
        return f"`[{self.category}]`类型的命令: \n" + "\n".join(
            f"- `{i.command}` | {i.description}" for i in self.commands
        )
