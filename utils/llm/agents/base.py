from abc import ABC, abstractmethod
from typing import Any, Type, Union, Optional, Generator, TypedDict

from strenum import StrEnum
from pydantic import Field, BaseModel

from ..message import Messages
from ..typings import ChatCompletionMessage, ChatCompletionToolParam, ChatCompletionMessageToolCall


class AgentStatus(StrEnum):
    """Agent状态"""

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
    agent: "BaseAgent"
    is_wait: bool


class BaseAgent(ABC, BaseModel):
    agents: dict[str, AgentDict] = {}
    status: AgentStatus = AgentStatus.init
    messages: Messages = Field(default_factory=Messages)
    root_agent: Optional["BaseAgent"] = None
    parent_agent: list["BaseAgent"] = []

    class Params(BaseModel):
        ...

    @classmethod
    def parameters(cls) -> dict:
        return cls.Params.schema()

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """agent的名称"""

    @classmethod
    def description(cls) -> str:
        """agent的描述"""
        return cls.__doc__ or ""

    def link_to(self, agent: Union[Type["BaseAgent"], "BaseAgent"], is_wait: bool = False) -> "BaseAgent":
        """与另一个agent建立联系

        Args:
            agent (Union[Type["BaseAgent"], "BaseAgent"]): agent
            is_wait (bool, optional): 是否等待上一个agent执行完成后执行. Defaults to False.

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
        """执行agent"""

    def functions(self) -> list[ChatCompletionToolParam]:
        return [
            agent["agent"].function() for agent in self.agents.values() if isinstance(agent["agent"], BaseFunctionAgent)
        ]


class BaseFunctionAgent(BaseAgent):
    @classmethod
    def function(cls) -> ChatCompletionToolParam:
        return {
            "type": "function",
            "function": {
                "name": cls.name(),
                "description": cls.description(),
                "parameters": cls.parameters(),
            },
        }

    def call_tools(self, message: Messages) -> Generator[ChatCompletionMessageToolCall, Any, None]:
        context = message[-1]
        if isinstance(context, ChatCompletionMessage) and context.tool_calls:
            for tool in context.tool_calls:
                if tool.function.name == self.name():
                    yield tool


class BaseChoiceFunctionAgent(BaseFunctionAgent):
    ...
