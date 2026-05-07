from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from utils.helper import Helpers

from ..command_tools import CommandToolCatalog
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

    def resolve_candidate_commands(self, candidate_commands: Iterable[str] | None) -> set[str]:
        """把 Planner 产出的候选命令解析为当前真实存在的命令名。"""

        if not candidate_commands:
            return set()
        return self.command_tools.resolve_commands(candidate_commands)
