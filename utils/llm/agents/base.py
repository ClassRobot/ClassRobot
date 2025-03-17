from asyncio import wait
from abc import ABC, abstractmethod
from typing import Any, Type, Union, NoReturn, Optional, Generator, TypedDict, overload

from strenum import StrEnum
from pydantic import BaseModel

from ..message import Messages
from .exception import SkipAgentException, FinishAgentException
from ..typings import ChatCompletionMessage, ChatCompletionToolParam, ChatCompletionMessageToolCall


class AgentStatus(StrEnum):
    """Agent状态"""

    success = "success"
    """成功"""
    failed = "failed"
    """失败"""
    running = "running"
    """执行中"""


class AgentDict(TypedDict):
    agent: "BaseAgent"
    is_wait: bool


class BaseAgent(ABC, BaseModel):
    agents: dict[str, AgentDict] = {}
    status: AgentStatus = AgentStatus.success
    messages: Messages = Messages()
    root_agent: Optional["BaseAgent"] = None

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
        agent.root_agent = self.root_agent or self
        self.agents[agent.name()] = {"agent": agent, "is_wait": is_wait}
        return agent

    async def invoke(self, messages: Messages):
        self.messages = messages
        self.messages = await self.execute(messages)
        await self.auto_next(self.messages)

    def result(self) -> Messages:
        """获取执行结果"""
        return self.messages

    @overload
    def next(self, name: str) -> AgentDict | None:
        ...

    @overload
    def next(self) -> list[AgentDict]:
        ...

    def next(self, name: str | None = None) -> AgentDict | list[AgentDict] | None:
        """execute结束后向后面的agent传递消息"""
        if name:
            return self.agents.get(name)
        return list(self.agents.values())

    async def auto_next(self, messages: Messages):
        all_tasks: list[list] = []
        tasks = []
        for agent in self.next():
            if not agent["is_wait"]:
                # 对于不需要等待的agent，一起执行
                tasks.append(agent["agent"].invoke(messages))
            else:
                # 对于需要等待的agent，单独执行
                all_tasks.append(tasks)
                all_tasks.append([agent["agent"].invoke(messages)])
                tasks = []
        all_tasks.append(tasks)
        all_tasks = [task for task in all_tasks if task]
        for task in all_tasks:
            await wait(task)

    async def finish(self) -> NoReturn:
        """结束agent"""
        raise FinishAgentException

    async def skip(self) -> NoReturn:
        """跳过agent, 直接执行下一个agent(这种方式下一个agent)"""
        await self.auto_next(self.messages)
        raise SkipAgentException

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
