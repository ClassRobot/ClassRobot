from collections import defaultdict
from typing import Iterable, Generator

from nonebot import logger
from strenum import StrEnum
from utils.roles import UserRole
from pydantic import BaseModel, Field, validator


class ParamMode(StrEnum):
    """定义命令参数数量约束的枚举值。"""

    OPTIONAL = "?"
    """可选参数"""
    ONE_OR_MORE = "+"
    """至少一个参数"""
    ZERO_OR_MORE = "*"
    """零个或多个参数"""


class HelperScope(StrEnum):
    """帮助菜单中的展示目录。"""

    public = "public"
    """公共命令"""
    user = "user"
    """普通用户命令"""
    student = "student"
    """学生身份命令"""
    teacher = "teacher"
    """教师身份命令"""
    admin = "admin"
    """管理员命令"""


HELPER_SCOPE_ORDER = (
    HelperScope.public,
    HelperScope.user,
    HelperScope.student,
    HelperScope.teacher,
    HelperScope.admin,
)

HELPER_SCOPE_TITLES = {
    HelperScope.public: "公共命令",
    HelperScope.user: "普通用户命令",
    HelperScope.student: "学生身份命令",
    HelperScope.teacher: "教师身份命令",
    HelperScope.admin: "管理员命令",
}

HELPER_SCOPE_DESCRIPTIONS = {
    HelperScope.public: "不依赖业务身份，任何人都可以直接使用。",
    HelperScope.user: "账号级通用能力，学生和教师也会继承可用。",
    HelperScope.student: "学生身份可用，或用于成为学生身份的相关流程。",
    HelperScope.teacher: "教师身份可用，或用于成为教师身份的相关流程。",
    HelperScope.admin: "仅管理员可用，请谨慎执行。",
}

STUDENT_SCOPED_ROLES = {UserRole.student, UserRole.class_cadre}
PLAIN_USER_ROLES = {UserRole.user}


def _normalize_roles(roles: Iterable[UserRole | str]) -> set[UserRole]:
    """把传入的角色枚举或字符串统一转换成 `UserRole` 集合。"""

    normalized: set[UserRole] = set()
    for role in roles:
        if isinstance(role, UserRole):
            normalized.add(role)
            continue
        try:
            normalized.add(UserRole(role))
        except ValueError:
            continue
    return normalized


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
        """校验参数名称是否合法。"""

        if not value:
            raise ValueError("参数名不能为空")
        if any(mode in value for mode in ParamMode):
            raise ValueError("参数名不能包含特殊字符")
        return value

    def __str__(self) -> str:
        """返回字符串表示。"""
        return self.name + (self.mode or "")


class Helper(BaseModel):
    """描述一条命令的帮助、鉴权与目录元数据。"""

    command: str
    """命令名称"""
    description: str
    """命令描述"""
    ai_description: str | None = None
    """描述给AI的提示"""
    tags: set[str] = Field(default_factory=set)
    """命令标签"""
    roles: set[UserRole] = Field(default_factory=set)
    """命令允许的角色集合，按“任一命中即可”处理。留空表示公共命令。"""
    exclude_roles: set[UserRole] = Field(default_factory=set)
    """明确禁止使用该命令的角色集合。"""
    scopes: set[HelperScope] = Field(default_factory=set)
    """帮助菜单展示目录；留空时会根据角色自动推断。"""
    params: list[Param] = Field(default_factory=list)
    """命令参数"""
    aliases: set[str] = Field(default_factory=set)
    """命令别名"""
    example: list[Context] = Field(default_factory=list)
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

    @property
    def display_scopes(self) -> set[HelperScope]:
        """返回帮助菜单中应出现的目录集合。"""

        if self.scopes:
            return set(self.scopes)
        if not self.roles:
            return {HelperScope.public}

        scopes: set[HelperScope] = set()
        if self.roles.intersection({UserRole.user}):
            scopes.add(HelperScope.user)
        if self.roles.intersection(STUDENT_SCOPED_ROLES):
            scopes.add(HelperScope.student)
        if self.roles.intersection({UserRole.teacher}):
            scopes.add(HelperScope.teacher)
        if self.roles.intersection({UserRole.admin}):
            scopes.add(HelperScope.admin)
        return scopes or {HelperScope.user}

    def is_command(self, command: str) -> bool:
        """查看是否为指定命令。"""

        command = command.strip()
        return command == self.command or command in self.aliases

    def is_available_for(self, *roles: UserRole | str) -> bool:
        """判断当前角色集合是否允许使用该命令。"""

        role_values = {str(role) for role in _normalize_roles(roles)}
        allow_values = {str(role) for role in self.roles}
        deny_values = {str(role) for role in self.exclude_roles}

        if deny_values.intersection(role_values):
            return False
        if allow_values and allow_values.isdisjoint(role_values):
            return False
        return True

    def visible_scopes_for(self, *roles: UserRole | str) -> set[HelperScope]:
        """返回当前角色集合下真正应该展示的目录。

        说明：
        - 学生和教师都能用的命令，不应该在单一身份下同时展示到两个目录。
        - 纯普通用户仍需要看到“加入班级 / 创建教师身份”这类带身份导向的入口命令。
        """

        scopes = self.display_scopes
        normalized_roles = _normalize_roles(roles)
        if not normalized_roles:
            return scopes

        is_plain_user = normalized_roles == PLAIN_USER_ROLES
        visible_scopes: set[HelperScope] = set()

        for scope in scopes:
            if scope in {HelperScope.public, HelperScope.user}:
                visible_scopes.add(scope)
            elif scope == HelperScope.student:
                if is_plain_user or normalized_roles.intersection(STUDENT_SCOPED_ROLES):
                    visible_scopes.add(scope)
            elif scope == HelperScope.teacher:
                if is_plain_user or UserRole.teacher in normalized_roles:
                    visible_scopes.add(scope)
            elif scope == HelperScope.admin:
                if UserRole.admin in normalized_roles:
                    visible_scopes.add(scope)

        # 若 helper 的显式 scopes 与角色元数据暂时不一致，退回原始目录，
        # 这样至少不会把本该可见的命令完全隐藏掉。
        return visible_scopes or scopes

    def to_string(self) -> str:
        """输出完整帮助文本。"""

        return (
            f"命令 | {self.command}\n"
            f"参数 | {', '.join(map(str, self.params)) or '无'}\n"
            f"别名 | {', '.join(sorted(self.aliases)) or '无'}\n"
            f"描述 | {self.description}\n"
            f"示例 | \n{self.example_text or '无'}"
        )

    def overview(self) -> str:
        """输出简要帮助文本。"""

        return (
            f"命令 | {self.command}\n"
            f"参数 | {', '.join(map(str, self.params)) or '无'}\n"
            f"别名 | {', '.join(sorted(self.aliases)) or '无'}\n"
            f"描述 | {self.description}\n"
        )

    def ai_overview(self) -> str:
        """输出提供给大模型使用的精简命令说明。"""

        text = (
            f"命令 | {self.command}\n"
            f"别名 | {', '.join(sorted(self.aliases)) or '无'}\n"
            f"描述 | {self.description}\n"
        )
        if self.ai_description:
            text += f"重点提示 | {self.ai_description}\n"
        return text


class HelperGroup(BaseModel):
    """帮助菜单中的一个目录分组。"""

    key: HelperScope
    title: str
    description: str
    helpers: list[Helper] = Field(default_factory=list)


class Helpers(BaseModel):
    """维护帮助信息集合，并提供检索、筛选、分组与渲染能力。"""

    helpers: list[Helper] = Field(default_factory=list)
    helper_search: dict[str, Helper] = Field(default_factory=dict)
    active_roles: set[UserRole] = Field(default_factory=set)

    def clear(self) -> None:
        """清空当前帮助集合。"""

        self.helpers.clear()
        self.helper_search.clear()
        self.active_roles.clear()

    def get_helper(self, command: str) -> Helper | None:
        """按命令名称或别名获取帮助信息。"""

        return self.helper_search.get(command)

    def get_tags_helpers(self, *tags: str) -> "Helpers":
        """按标签筛选帮助信息。"""

        helpers = Helpers()
        helpers.extend(helper for helper in self.helpers if not helper or helper.tags.intersection(tags))
        return helpers

    def get_roles_helpers(self, *roles: UserRole | str) -> "Helpers":
        """按角色筛选当前可使用的帮助信息。"""

        helpers = Helpers()
        helpers.active_roles = _normalize_roles(roles)
        helpers.extend(helper for helper in self.helpers if helper.is_available_for(*roles))
        return helpers

    def group_by_scopes(self, *roles: UserRole | str) -> list[HelperGroup]:
        """按帮助目录分组。

        传入 `roles` 时会先按角色过滤；不传时默认直接对当前集合分组。
        """

        current_roles = _normalize_roles(roles) if roles else set(self.active_roles)
        source = self.get_roles_helpers(*current_roles) if roles else self
        grouped: dict[HelperScope, list[Helper]] = defaultdict(list)
        for helper in source.helpers:
            visible_scopes = helper.visible_scopes_for(*current_roles) if current_roles else helper.display_scopes
            for scope in visible_scopes:
                grouped[scope].append(helper)

        return [
            HelperGroup(
                key=scope,
                title=HELPER_SCOPE_TITLES[scope],
                description=HELPER_SCOPE_DESCRIPTIONS[scope],
                helpers=grouped[scope],
            )
            for scope in HELPER_SCOPE_ORDER
            if grouped.get(scope)
        ]

    def extend(self, helpers: Iterable[Helper]):
        """向当前帮助集合批量追加帮助项。"""

        for helper in helpers:
            self.append(helper)

    def append(self, helper: Helper):
        """追加一条帮助信息并同步更新命令索引。"""

        helper.aliases -= {helper.command}
        if not helper.example:
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
        for command in helper.commands:
            if command in self.helper_search:
                logger.warning(f"command {command} already exists")
            else:
                self.helper_search[command] = helper

    def __iter__(self) -> Generator[Helper, None, None]:
        """返回迭代器。"""

        yield from self.helpers

    async def render_pic(self) -> bytes:
        """将当前帮助集合渲染为图片。"""

        from nonebot_plugin_htmlrender import template_to_pic

        from utils.config import template_dir

        return await template_to_pic(
            str(template_dir),
            "helper.html",
            {
                "helpers": self.helpers,
                "groups": self.group_by_scopes(),
            },
        )

    def to_string(self):
        """将当前帮助集合转换为文本列表。"""

        return "\n".join(helper.overview() for helper in self.helpers)
