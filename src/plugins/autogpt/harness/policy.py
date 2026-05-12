from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from utils.helper import Helpers

from ..command_tools import CommandTool, CommandToolCatalog
from ..knowledge import AgentSkillCatalog


@dataclass(slots=True)
class AgentPolicyHarness:
    """聚合 AutoGPT 的策略层依赖。

    这一层承载“当前允许模型看到和规划什么”：

    - 当前用户可见的命令集合
    - 结构化命令目录
    - 运行时可用 Skill 摘要
    """

    helpers: Helpers
    skill_catalog: AgentSkillCatalog = field(default_factory=AgentSkillCatalog)
    command_tools: CommandToolCatalog = field(init=False)

    def __post_init__(self) -> None:
        self.command_tools = CommandToolCatalog.from_helpers(self.helpers)

    @property
    def skill_catalog_prompt(self) -> str:
        """把 Skill 注册表转换成 Prompt 可直接消费的摘要。"""

        return self.skill_catalog.to_prompt()

    def render_command_tools_prompt(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
        candidate_commands: Iterable[str] | None = None,
    ) -> str:
        """按当前问题裁剪命令目录，减少无关 Prompt 载荷。"""

        tools = self.select_command_tools(
            query=query,
            limit=limit,
            candidate_commands=candidate_commands,
        )
        return self.render_command_tools_prompt_from_tools(tools)

    def render_skill_catalog_prompt(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
        skill_names: Iterable[str] | None = None,
    ) -> str:
        """按当前问题裁剪 Skill 目录，减少无关 Prompt 载荷。"""

        summaries = self.select_skill_summaries(
            query=query,
            limit=limit,
            skill_names=skill_names,
        )
        return self.render_skill_catalog_prompt_from_summaries(summaries)

    def resolve_candidate_commands(self, candidate_commands: Iterable[str] | None) -> set[str]:
        """把 Planner 产出的候选命令解析为当前真实存在的命令名。"""

        if not candidate_commands:
            return set()
        return self.command_tools.resolve_commands(candidate_commands)

    def select_command_tools(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
        candidate_commands: Iterable[str] | None = None,
    ) -> list[CommandTool]:
        """按当前问题或候选命令挑选要暴露给模型的命令子集。"""

        return self.command_tools.select_tools(
            query=query,
            limit=limit,
            candidate_commands=candidate_commands,
        )

    def select_skill_summaries(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
        skill_names: Iterable[str] | None = None,
    ) -> list[dict[str, str]]:
        """按当前问题或显式技能名挑选要暴露给模型的 Skill 子集。"""

        return self.skill_catalog.select_summaries(
            query=query,
            limit=limit,
            skill_names=skill_names,
        )

    @staticmethod
    def render_command_tools_prompt_from_tools(tools: Iterable[CommandTool]) -> str:
        """把已选中的命令工具列表渲染为紧凑 Prompt 片段。"""

        lines = [tool.to_prompt() for tool in tools]
        return "\n".join(lines) if lines else "暂无可用命令。"

    @staticmethod
    def render_skill_catalog_prompt_from_summaries(summaries: Iterable[dict[str, str]]) -> str:
        """把已选中的 Skill 摘要渲染为紧凑 Prompt 片段。"""

        lines = [f"- {item['name']}: {item['description']}" for item in summaries]
        return "\n".join(lines) if lines else "暂无可用 Skill。"
