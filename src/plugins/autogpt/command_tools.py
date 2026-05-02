import hashlib
from typing import Iterator, Iterable, Literal

from pydantic import Field, BaseModel
from utils.helper import Helper, Helpers, ParamMode
from utils.helper import Param as HelperParam


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

    def to_prompt(self) -> str:
        """转换成适合提示词阅读的参数说明。"""

        flags = []
        if self.required:
            flags.append("必填")
        else:
            flags.append("可选")
        if self.multiple:
            flags.append("可多值")
        description = f"：{self.description}" if self.description else ""
        return f"- {self.name} ({'，'.join(flags)}){description}"


class CommandTool(BaseModel):
    """把 Helper 命令包装成可被 Agent 规划与后续工具调用识别的工具。"""

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
    def from_helper(cls, helper: Helper) -> "CommandTool":
        """从 Helper 构建命令工具描述。"""

        return cls(
            name=_safe_tool_name(helper.command),
            command=helper.command,
            description=helper.description,
            ai_description=helper.ai_description or "",
            aliases=sorted(helper.aliases),
            params=[_param_from_helper_param(param) for param in helper.params],
            risk_level=_infer_risk_level(helper),
        )

    @property
    def command_names(self) -> set[str]:
        """返回真实命令和别名集合。"""

        return {self.command, *self.aliases}

    def to_prompt(self) -> str:
        """转换成面向 Planner/AutoTask 的稳定命令工具说明。"""

        aliases = "、".join(self.aliases) if self.aliases else "无"
        params = "\n".join(param.to_prompt() for param in self.params) or "- 无"
        prompt = (
            f"工具名 | {self.name}\n"
            f"真实命令 | {self.command}\n"
            f"别名 | {aliases}\n"
            f"风险 | {self.risk_level}\n"
            f"描述 | {self.description}\n"
            f"参数 |\n{params}\n"
        )
        if self.ai_description:
            prompt += f"重点提示 | {self.ai_description}\n"
        return prompt

    def to_openai_tool(self) -> dict:
        """转换成后续 function calling 可使用的工具描述。

        当前 AutoGPT 仍通过 `handle_event()` 执行命令；这里先产出稳定
        schema，后续工具循环可以直接复用。
        """

        properties: dict[str, dict] = {}
        required: list[str] = []
        for param in self.params:
            schema: dict = {"type": "string", "description": param.description or param.name}
            if param.multiple:
                schema = {
                    "type": "array",
                    "items": {"type": "string"},
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
        """从当前用户可见 Helper 集合生成命令工具目录。"""

        catalog = cls()
        for helper in helpers:
            catalog.append(CommandTool.from_helper(helper))
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

    def to_prompt(self) -> str:
        """渲染完整工具目录，供 Planner 和任务生成使用。"""

        return "\n".join(tool.to_prompt() for tool in self.tools)

    def __iter__(self) -> Iterator[CommandTool]:
        yield from self.tools

    def __bool__(self) -> bool:
        return bool(self.tools)


def _safe_tool_name(command: str) -> str:
    digest = hashlib.md5(command.encode("utf-8")).hexdigest()[:10]
    return f"command_{digest}"


def _param_from_helper_param(param: HelperParam) -> CommandToolParam:
    mode = param.mode
    required = mode not in {ParamMode.OPTIONAL, ParamMode.ZERO_OR_MORE}
    multiple = mode in {ParamMode.ONE_OR_MORE, ParamMode.ZERO_OR_MORE}
    return CommandToolParam(
        name=param.name,
        description=param.description or "",
        required=required,
        multiple=multiple,
    )


def _infer_risk_level(helper: Helper) -> RiskLevel:
    text = f"{helper.command} {helper.description} {helper.ai_description or ''}"
    high_keywords = ("删除", "清空", "批量", "通知", "公告", "群发", "移除")
    medium_keywords = (
        "添加",
        "新增",
        "创建",
        "修改",
        "更新",
        "绑定",
        "设置",
        "提交",
        "导入",
        "加入",
        "退出",
        "请假",
        "注销",
    )
    if any(keyword in text for keyword in high_keywords):
        return "high"
    if any(keyword in text for keyword in medium_keywords):
        return "medium"
    return "low"
