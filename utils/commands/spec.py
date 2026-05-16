from __future__ import annotations

from pydantic import BaseModel, Field
from utils.roles import UserRole
from utils.helper import Context, HelperScope

from .schema import CommandExecutionMode, CommandParam, CommandRiskLevel


class CommandSpec(BaseModel):
    """描述一条项目命令的单一事实来源。

    一条命令的帮助展示、Agent 工具、管理端命令目录和权限策略，
    都应尽量从该模型派生，避免在 matcher、Helper 和 Agent tool
    之间重复维护同一份信息。
    """

    name: str
    aliases: set[str] = Field(default_factory=set)
    description: str
    ai_description: str = ""
    params: list[CommandParam] = Field(default_factory=list)
    roles: set[UserRole] = Field(default_factory=set)
    exclude_roles: set[UserRole] = Field(default_factory=set)
    scopes: set[HelperScope] = Field(default_factory=set)
    tags: set[str] = Field(default_factory=set)
    examples: list[Context] = Field(default_factory=list)
    risk_level: CommandRiskLevel = "low"
    agent_callable: bool = True
    execution_mode: CommandExecutionMode = "matcher"
    plugin_module: str | None = None

    @property
    def commands(self) -> set[str]:
        """返回主命令与全部别名。

        Returns:
            set[str]: 主命令名称和别名集合。
        """

        return {self.name, *self.aliases}
