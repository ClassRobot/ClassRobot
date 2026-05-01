from typing import Any
from dataclasses import dataclass, field

from utils.llm.message import Messages


@dataclass(slots=True)
class ToolCallResult:
    """一次工具调用的执行结果。

    这个结构主要用于调试、日志和后续审计：业务方可以看到模型调用了
    哪个工具、传了什么参数、工具返回了什么，以及是否执行成功。
    """

    name: str
    arguments: dict[str, Any]
    result: str
    success: bool = True


@dataclass(slots=True)
class AgentResponse:
    """智能体最终返回结果。

    `content` 是最常用的自然语言回复；`messages` 保留完整上下文，
    可以继续传给下一轮；`tool_calls` 记录本轮发生过的工具调用。
    """

    content: str
    messages: Messages
    tool_calls: list[ToolCallResult] = field(default_factory=list)

    def __str__(self) -> str:
        return self.content
