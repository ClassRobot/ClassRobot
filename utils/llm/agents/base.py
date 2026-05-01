from abc import ABC, abstractmethod
from typing import Any, Type, Union, Optional, Generator, TypedDict

from strenum import StrEnum
from pydantic import Field, BaseModel

from ..message import Messages
from ..typings import ChatCompletionMessage, ChatCompletionToolParam, ChatCompletionMessageToolCall


class AgentStatus(StrEnum):
    """定义智能体执行过程中的状态值。"""

    success = "success"
    """成功"""
    failed = "failed"
    """失败"""
    running = "running"
    """执行中"""
    finish = "finish"
    """结束当前agent"""
    skip = "skip"
    """跳过当前agent"""
    init = "init"
    """初始化状态"""


class AgentDict(TypedDict):
    """描述子智能体注册信息的数据结构。"""

    agent: "BaseAgent"
    is_wait: bool


class BaseAgent(ABC, BaseModel):
    """定义智能体的基础状态、消息上下文和编排能力。"""

    agents: dict[str, AgentDict] = Field(default_factory=dict)
    status: AgentStatus = AgentStatus.init
    messages: Messages = Field(default_factory=Messages)
    root_agent: Optional["BaseAgent"] = None
    parent_agent: list["BaseAgent"] = Field(default_factory=list)

    class Params(BaseModel):
        """定义当前智能体可接收的工具参数结构。"""

        ...

    @classmethod
    def parameters(cls) -> dict:
        """返回当前智能体的参数模式定义。

        返回:
            dict: 可供函数调用工具注册使用的 JSON Schema。
        """
        return cls.Params.schema()

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """返回智能体的唯一名称。"""

    @classmethod
    def description(cls) -> str:
        """返回智能体的说明文本。

        返回:
            str: 默认使用类文档字符串作为描述内容。
        """
        return cls.__doc__ or ""

    def link_to(self, agent: Union[Type["BaseAgent"], "BaseAgent"], is_wait: bool = False) -> "BaseAgent":
        """将当前智能体与另一个智能体连接成执行链。

        参数:
            agent (Union[Type["BaseAgent"], BaseAgent]): 要连接的智能体类型或实例。
            is_wait (bool, optional): 是否等待当前节点执行完成后再调度目标智能体。默认为 `False`。

        Example:

        ```python
        agent1 = Agent1()

        agent1.link_to(Agent2).link_to(agent1)  # agent1与agent2建立联系然后传回agent1
        agent1.link_to(Agent3).link_to(agent1)  # agent1建立agent2与agent3两条分支然后传回agent1
        await agent1.invoke(messages)
        print(agent1.result())
        ```
        """
        if not isinstance(agent, BaseAgent):
            agent = agent()
        agent.parent_agent.append(self)
        agent.root_agent = self.root_agent or self
        self.agents[agent.name()] = {"agent": agent, "is_wait": is_wait}
        return agent

    @abstractmethod
    async def execute(self, messages: Messages) -> Messages:
        """执行当前智能体的核心逻辑。

        参数:
            messages (Messages): 当前会话的消息上下文。

        返回:
            Messages: 处理后的消息上下文。
        """

    def functions(self) -> list[ChatCompletionToolParam]:
        """收集当前已链接的函数型智能体工具定义。

        返回:
            list[ChatCompletionToolParam]: 当前智能体可转交调用的工具列表。
        """
        return [
            agent["agent"].function() for agent in self.agents.values() if isinstance(agent["agent"], BaseFunctionAgent)
        ]


class BaseFunctionAgent(BaseAgent):
    """定义可被大模型当作函数工具调用的智能体基类。"""

    @classmethod
    def function(cls) -> ChatCompletionToolParam:
        """生成当前智能体对应的函数调用描述。

        返回:
            ChatCompletionToolParam: 提供给大模型函数调用能力的工具定义。
        """
        return {
            "type": "function",
            "function": {
                "name": cls.name(),
                "description": cls.description(),
                "parameters": cls.parameters(),
            },
        }

    def call_tools(self, message: Messages) -> Generator[ChatCompletionMessageToolCall, Any, None]:
        """筛选最后一条模型消息中属于当前智能体的工具调用。

        参数:
            message (Messages): 当前会话的消息集合。

        返回:
            Generator[ChatCompletionMessageToolCall, Any, None]: 当前智能体需要处理的工具调用迭代器。
        """
        context = message[-1]
        if isinstance(context, ChatCompletionMessage) and context.tool_calls:
            for tool in context.tool_calls:
                if tool.function.name == self.name():
                    yield tool


class BaseChoiceFunctionAgent(BaseFunctionAgent):
    """定义需要用户或模型从多个候选项中选择的函数型智能体基类。"""

    ...
