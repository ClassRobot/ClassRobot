from typing import Literal, Iterable, Iterator

from pydantic import Field, BaseModel

from utils.helper import Helpers
from utils.commands.renderers.tool import safe_tool_name

from .prompt_selection import score_prompt_relevance

RiskLevel = Literal["low", "medium", "high"]


class CommandToolParam(BaseModel):
    """Agent 视角下的项目命令参数说明。"""

    name: str
    """参数名称。"""
    description: str = ""
    """参数用途说明。"""
    required: bool = True
    """参数是否必填。"""
    multiple: bool = False
    """参数是否可以出现多次。"""
    value_type: str = "string"
    """OpenAI tool schema 中使用的 JSON 基础类型。"""

    def to_prompt(self) -> str:
        """转换成适合提示词阅读的紧凑参数说明。"""

        flags = ["必填" if self.required else "可选"]
        if self.multiple:
            flags.append("多值")
        description = f"：{self.description}" if self.description else ""
        return f"{self.name}[{'/'.join(flags)}]{description}"


class CommandTool(BaseModel):
    """把 service-style 项目命令包装成可被 Agent 规划和调用的工具。"""

    name: str
    """function calling 使用的安全工具名。"""
    command: str
    """项目中的真实命令名。"""
    description: str
    """命令描述。"""
    ai_description: str = ""
    """给模型看的额外约束。"""
    aliases: list[str] = Field(default_factory=list)
    """命令别名。"""
    params: list[CommandToolParam] = Field(default_factory=list)
    """结构化参数说明。"""
    risk_level: RiskLevel = "low"
    """该命令的默认风险等级。"""

    @classmethod
    def from_spec(cls, spec) -> "CommandTool":
        """从统一 CommandSpec 构建命令工具描述。"""

        return cls(
            name=safe_tool_name(spec.name),
            command=spec.name,
            description=spec.description,
            ai_description=spec.ai_description or "",
            aliases=sorted(spec.aliases),
            params=[
                CommandToolParam(
                    name=param.name,
                    description=param.description or "",
                    required=param.required,
                    multiple=param.multiple,
                    value_type=param.value_type,
                )
                for param in spec.params
            ],
            risk_level=spec.risk_level,
        )

    @property
    def command_names(self) -> set[str]:
        """返回真实命令和别名集合。"""

        return {self.command, *self.aliases}

    def to_prompt(self) -> str:
        """转换成面向 Planner 和 AutoTask 的紧凑命令摘要。"""

        aliases = "、".join(self.aliases)
        params = "；".join(param.to_prompt() for param in self.params) if self.params else "无"
        sections = [f"- {self.command}: {self.description}"]
        if self.aliases:
            sections.append(f"别名={aliases}")
        sections.append(f"风险={self.risk_level}")
        sections.append(f"参数={params}")
        if self.ai_description:
            sections.append(f"提示={self.ai_description}")
        return " | ".join(sections)

    def __str__(self) -> str:
        """返回适合直接注入提示词的命令摘要。"""

        return self.to_prompt()

    def to_openai_tool(self) -> dict:
        """转换成后续 function calling 可使用的工具描述。

        Agent 只暴露已经接入 `CommandExecutor` 的 service-style 命令，
        因此这里生成的 schema 与实际执行入口保持一一对应。
        """

        properties: dict[str, dict] = {}
        required: list[str] = []
        for param in self.params:
            schema: dict = {"type": param.value_type, "description": param.description or param.name}
            if param.multiple:
                schema = {
                    "type": "array",
                    "items": {"type": param.value_type},
                    "description": param.description or param.name,
                }
            properties[param.name] = schema
            if param.required:
                required.append(param.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class CommandToolCatalog(BaseModel):
    """当前用户可见的项目命令工具集合。"""

    tools: list[CommandTool] = Field(default_factory=list)
    command_index: dict[str, CommandTool] = Field(default_factory=dict)
    tool_index: dict[str, CommandTool] = Field(default_factory=dict)

    @classmethod
    def from_helpers(cls, helpers: Helpers) -> "CommandToolCatalog":
        """从当前用户可见 Helper 集合生成 service 命令工具目录。

        Helper 只负责限定“当前用户看得见哪些命令”。真正进入 Agent
        工具目录的命令必须已经注册 `CommandSpec` 且
        `execution_mode="service"`，避免 Agent 绕过统一执行器。
        """

        from utils.commands.registry import command_registry
        from utils.commands.availability import command_availability
        from utils.commands.executor import command_executor

        catalog = cls()
        for helper in helpers:
            spec = command_registry.get(helper.command)
            if spec is None:
                continue
            availability = command_availability.check(spec)
            if (
                not availability.available
                or not spec.agent_callable
                or spec.execution_mode != "service"
                or not command_executor.has_handler(spec.name)
            ):
                continue
            catalog.append(CommandTool.from_spec(spec))
        return catalog

    def append(self, tool: CommandTool) -> None:
        """追加命令工具并建立真实命令、别名和工具名索引。"""

        self.tools.append(tool)
        self.tool_index[tool.name] = tool
        for command_name in tool.command_names:
            self.command_index[command_name] = tool

    def get(self, command_or_tool_name: str) -> CommandTool | None:
        """按真实命令、别名或工具名查找命令工具。"""

        return self.command_index.get(command_or_tool_name) or self.tool_index.get(command_or_tool_name)

    def resolve_commands(self, command_names: Iterable[str]) -> set[str]:
        """把候选命令或工具名解析成真实命令名。"""

        commands: set[str] = set()
        for command_name in command_names:
            if tool := self.get(command_name):
                commands.add(tool.command)
        return commands

    def select_tools(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
        candidate_commands: Iterable[str] | None = None,
    ) -> list[CommandTool]:
        """按候选命令或自然语言查询挑选最相关的命令子集。"""

        if candidate_commands:
            selected = self.select_candidate_tools(candidate_commands)
            if selected:
                return selected[:limit] if limit is not None else selected

        selected = list(self.tools)
        if query:
            selected = self.select_relevant_tools(query, limit=limit)

        if limit is not None:
            selected = selected[:limit]
        return selected

    def to_prompt(
        self,
        *,
        query: str | None = None,
        limit: int | None = None,
        candidate_commands: Iterable[str] | None = None,
    ) -> str:
        """渲染完整或裁剪后的命令目录，供 Planner 和任务生成使用。"""

        selected = self.select_tools(query=query, limit=limit, candidate_commands=candidate_commands)
        if not selected:
            return "暂无可用命令。"
        return "\n".join(tool.to_prompt() for tool in selected)

    def __str__(self) -> str:
        """返回适合直接注入提示词的命令目录摘要。"""

        return self.to_prompt()

    def __iter__(self) -> Iterator[CommandTool]:
        yield from self.tools

    def __bool__(self) -> bool:
        return bool(self.tools)

    def select_candidate_tools(self, candidate_commands: Iterable[str]) -> list[CommandTool]:
        """按显式候选命令解析命令目录子集。"""

        selected: list[CommandTool] = []
        seen: set[str] = set()
        for command_name in candidate_commands:
            tool = self.get(command_name)
            if tool is None or tool.command in seen:
                continue
            selected.append(tool)
            seen.add(tool.command)
        return selected

    def select_relevant_tools(self, query: str, *, limit: int | None = None) -> list[CommandTool]:
        """按自然语言问题挑选最相关的命令子集。"""

        scored: list[tuple[int, int, CommandTool]] = []
        for index, tool in enumerate(self.tools):
            score = score_prompt_relevance(
                query,
                names=tool.command_names,
                texts=(
                    tool.description,
                    tool.ai_description,
                    *(param.name for param in tool.params),
                    *(param.description for param in tool.params if param.description),
                ),
            )
            if score > 0:
                scored.append((score, index, tool))

        scored.sort(key=lambda item: (-item[0], item[1]))
        selected = [tool for _, _, tool in scored]
        if limit is None or len(selected) >= limit:
            return selected

        seen = {tool.command for tool in selected}
        for tool in self.tools:
            if tool.command in seen:
                continue
            selected.append(tool)
            seen.add(tool.command)
            if len(selected) >= limit:
                break
        return selected
