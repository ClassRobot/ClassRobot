from __future__ import annotations

from typing import Iterable
from dataclasses import field, dataclass

from src.platform.helper import Helpers
from src.core.mcp import MCPClient, MCPToolCatalog

from ..knowledge import SkillCatalog
from ..capabilities import RuntimeCapabilityCatalog
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
    mcp_client: MCPClient = field(default_factory=MCPClient)
    mcp_tools: MCPToolCatalog = field(default_factory=MCPToolCatalog)
    command_tools: CommandToolCatalog = field(init=False)
    _mcp_tools_loaded: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.command_tools = CommandToolCatalog.from_helpers(self.helpers)

    @property
    def skill_catalog_prompt(self) -> str:
        """把 Skill 注册表转换成 Prompt 可直接消费的摘要。"""

        return self.skill_catalog.to_prompt()

    @property
    def mcp_tools_loaded(self) -> bool:
        """返回当前轮次是否已经尝试加载 MCP tool 目录。"""

        return self._mcp_tools_loaded

    async def refresh_mcp_tools(self, *, force: bool = False) -> MCPToolCatalog:
        """按需刷新 MCP tool 目录；失败时保留空目录和错误说明。"""

        if self._mcp_tools_loaded and not force:
            return self.mcp_tools
        self.mcp_tools = await MCPToolCatalog.from_client(self.mcp_client)
        self._mcp_tools_loaded = True
        return self.mcp_tools

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

    def render_mcp_tools_prompt(
        self,
        *,
        limit: int | None = None,
        tool_names: Iterable[str] | None = None,
    ) -> str:
        """渲染 MCP tool 目录；只有 Planner 明确候选时才收窄。"""

        return self.mcp_tools.to_prompt(limit=limit, tool_names=tool_names)

    def capability_catalog(self) -> RuntimeCapabilityCatalog:
        """构建当前轮次的统一能力目录。"""

        return RuntimeCapabilityCatalog.build(command_tools=self.command_tools, mcp_tools=self.mcp_tools)

    def render_capability_catalog_prompt(self) -> str:
        """渲染 Agent 能力自知目录。"""

        return self.capability_catalog().to_prompt()

    def has_realtime_external_lookup(self) -> bool:
        """判断当前是否存在实时公共外部检索能力。"""

        return self.capability_catalog().has_realtime_external_lookup()

    def resolve_candidate_commands(self, candidate_commands: Iterable[str] | None) -> set[str]:
        """把 Planner 产出的候选命令解析为当前真实存在的命令名。"""

        if not candidate_commands:
            return set()
        return self.command_tools.resolve_commands(candidate_commands)

    def resolve_candidate_mcp_tools(self, candidate_tools: Iterable[str] | None) -> set[str]:
        """把 Planner 产出的 MCP 候选解析为当前真实存在的 tool 名称。"""

        return self.mcp_tools.resolve_tools(candidate_tools)

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
