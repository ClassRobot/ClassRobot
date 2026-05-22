from __future__ import annotations

from typing import Iterable
from dataclasses import field, dataclass

from src.platform.helper import Helpers

from ..knowledge import SkillCatalog
from ..command_tools import CommandTool, CommandToolCatalog


@dataclass(slots=True)
class PolicyHarness:
    """聚合 AutoGPT 的策略层依赖。

    这一层承载“当前允许模型看到和规划什么”：

    - 当前用户可见的命令集合
    - 结构化命令目录
    - 运行时可用 Skill 摘要
    """

    helpers: Helpers
    skill_catalog: SkillCatalog = field(default_factory=SkillCatalog)
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
        limit: int | None = None,
        candidate_commands: Iterable[str] | None = None,
    ) -> str:
        """渲染命令目录；只有 Planner 明确候选时才收窄。"""

        tools = self.select_command_tools(
            limit=limit,
            candidate_commands=candidate_commands,
        )
        return self.render_command_tools_prompt_from_tools(tools)

    def render_skill_catalog_prompt(
        self,
        *,
        limit: int | None = None,
        skill_names: Iterable[str] | None = None,
    ) -> str:
        """渲染 Skill 目录；只有 Planner 明确候选时才收窄。"""

        summaries = self.select_skill_summaries(
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
        limit: int | None = None,
        candidate_commands: Iterable[str] | None = None,
    ) -> list[CommandTool]:
        """按显式候选命令挑选命令；否则暴露完整可见目录。"""

        return self.command_tools.select_tools(
            limit=limit,
            candidate_commands=candidate_commands,
        )

    def select_skill_summaries(
        self,
        *,
        limit: int | None = None,
        skill_names: Iterable[str] | None = None,
    ) -> list[dict[str, str]]:
        """按显式 Skill 名挑选摘要；否则暴露完整 Skill 目录。"""

        return self.skill_catalog.select_summaries(
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
