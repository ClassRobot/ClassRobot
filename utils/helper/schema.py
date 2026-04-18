from typing import Iterable, Generator

from nonebot import logger
from strenum import StrEnum
from utils.roles import UserRole
from utils.config import template_dir
from pydantic import BaseModel, validator
from nonebot_plugin_htmlrender import template_to_pic


class ParamMode(StrEnum):
    """定义命令参数数量约束的枚举值。"""
    OPTIONAL = "?"
    """可选参数"""
    ONE_OR_MORE = "+"
    """至少一个参数"""
    ZERO_OR_MORE = "*"
    """零个或多个参数"""


class Context(BaseModel):
    """表示帮助示例中的一轮命令交互上下文。"""

    rote: str
    content: str

    def __str__(self) -> str:
        """返回字符串表示。"""
        return f"{self.rote}:\n\t{self.content}"


class Param(BaseModel):
    """描述单个命令参数的名称、说明与数量模式。"""

    name: str
    description: str | None = None
    mode: ParamMode | None = None

    @validator("name")
    def name_validator(cls, value: str) -> str:
        """校验参数名称是否合法。

        参数:
            value (str): 待校验的参数名称。

        返回:
            str: 通过校验后的参数名称。
        """
        if not value:
            raise ValueError("参数名不能为空")
        # name不能存在mode中的字符
        if any(mode in value for mode in ParamMode):
            raise ValueError("参数名不能包含特殊字符")
        return value

    def __str__(self) -> str:
        """返回字符串表示。"""
        return self.name + (self.mode or "")


class Helper(BaseModel):
    """描述一条命令的帮助信息，用于渲染帮助页和构建 AI 提示词。"""

    command: str
    """命令名称"""
    description: str
    """命令描述"""
    ai_description: str | None = None
    """描述给AI的提示"""
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
        """返回命令主名与全部别名的集合。"""
        return {self.command, *self.aliases}

    @property
    def example_text(self) -> str:
        """返回示例列表拼接后的文本表示。"""
        if isinstance(self.example, str):
            return self.example
        return "\n\n".join(map(str, self.example))

    def is_command(self, command: str) -> bool:
        """查看是否为指定命令

        参数:
            command (str): 命令名称或别名

        返回:
            bool: 是否为指定命令
        """
        command = command.strip()
        return command == self.command or command in self.aliases

    def to_string(self) -> str:
        """输出完整帮助文本。"""
        return (
            f"命令 | {self.command}\n"
            f"参数 | {', '.join(map(str, self.params)) or '无'}\n"
            f"别名 | {', '.join(self.aliases) or '无'}\n"
            f"描述 | {self.description}\n"
            f"示例 | \n{self.example_text or '无'}"
        )

    def overview(self) -> str:
        """输出简要帮助文本。"""
        return (
            f"命令 | {self.command}\n"
            f"参数 | {', '.join(map(str, self.params)) or '无'}\n"
            f"别名 | {', '.join(self.aliases) or '无'}\n"
            f"描述 | {self.description}\n"
        )

    def ai_overview(self) -> str:
        """输出提供给大模型使用的精简命令说明。

        返回:
            str: 适合放入提示词的命令说明文本。
        """
        text = f"命令 | {self.command}\n" f"别名 | {', '.join(self.aliases) or '无'}\n" f"描述 | {self.description}\n"
        if self.ai_description:
            text += f"重点提示 | {self.ai_description}\n"
        return text


class Helpers(BaseModel):
    """维护帮助信息集合，并提供检索、筛选与渲染能力。"""
    helpers: list[Helper] = []
    helper_search: dict[str, Helper] = {}

    def get_helper(self, command: str) -> Helper | None:
        """按命令名称或别名获取帮助信息。

        参数:
            command (str): 命令名称或别名。

        返回:
            Helper | None: 匹配到的帮助对象，不存在时返回 `None`。
        """
        return self.helper_search.get(command)

    def get_tags_helpers(self, *tags: str) -> "Helpers":
        """按标签筛选帮助信息。

        参数:
            tags (*str): 需要匹配的标签集合。

        返回:
            Helpers: 包含匹配结果的新帮助集合。
        """
        helpers = Helpers()
        helpers.extend(helper for helper in self.helpers if not helper or helper.tags.intersection(tags))
        return helpers

    def get_roles_helpers(self, *roles: UserRole) -> "Helpers":
        """按角色筛选帮助信息。

        参数:
            roles (*UserRole): 当前用户拥有的角色集合。

        返回:
            Helpers: 当前角色可使用的帮助集合。
        """
        helpers = Helpers()
        helpers.extend(helper for helper in self.helpers if not helper.roles or helper.roles.issubset(roles))
        return helpers

    def extend(self, helpers: Iterable[Helper]):
        """向当前帮助集合批量追加帮助项。

        参数:
            helpers (Iterable[Helper]): 待追加的帮助信息集合。
        """
        for helper in helpers:
            self.append(helper)

    def append(self, helper: Helper):
        """追加一条帮助信息并同步更新命令索引。

        参数:
            helper (Helper): 待加入集合的帮助信息对象。
        """
        helper.aliases -= {helper.command}
        if not helper.example:
            # Auto-generate a minimal runnable example so both the human help view
            # and the AI prompt builder still have a concrete usage pattern.
            helper.example = [
                Context(
                    rote=UserRole.user,
                    content=" ".join((helper.command, *(p.name for p in helper.params))),
                )
            ]
        if helper in self.helpers:
            logger.warning(f"helper {helper.command} already exists")
        else:
            self.helpers.append(helper)
        # The same registry feeds `help` and AI command planning, so every alias must
        # resolve back to the same helper definition.
        for command in helper.commands:
            if command in self.helper_search:
                # 命令别名重复
                logger.warning(f"command {command} already exists")
            else:
                self.helper_search[command] = helper

    def __iter__(self) -> Generator[Helper, None, None]:
        """返回迭代器。"""
        yield from self.helpers

    async def render_pic(self) -> bytes:
        """将当前帮助集合渲染为图片。

        返回:
            bytes: 渲染后的图片字节数据。
        """
        html = await template_to_pic(
            str(template_dir),
            "helper.html",
            {
                "helpers": self.helpers,
            },
        )
        return html

    def to_string(self):
        """将当前帮助集合转换为文本列表。"""
        return "\n".join(helper.overview() for helper in self.helpers)
