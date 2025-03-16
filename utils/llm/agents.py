from asyncio import wait
from abc import ABC, abstractmethod
from typing import Type, Union, TypedDict, overload

from pydantic import BaseModel

from .schema import Messages


class AgentDict(TypedDict):
    agent: "BaseAgent"
    is_wait: bool


class BaseAgent(ABC, BaseModel):
    agents: dict[str, AgentDict] = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """agent的名称"""

    def link_to(self, agent: Union[Type["BaseAgent"], "BaseAgent"], is_wait: bool = False) -> "BaseAgent":
        """与另一个agent建立联系

        Args:
            agent (Union[Type["BaseAgent"], "BaseAgent"]): agent
            is_wait (bool, optional): 是否等待上一个agent执行完成后执行. Defaults to False.

        Example:

        ```python
        agent1 = Agent1()
        agent2 = Agent2
        agent3 = Agent3

        agent1.link_to(agent2).link_to(agent1)  # agent1与agent2建立联系然后传回agent1
        agent1.link_to(agent3).link_to(agent1)  # agent1与agent3建立联系然后传回agent2
        await agent1.invoke(messages)
        print(agent1.result())
        ```
        """
        if not isinstance(agent, BaseAgent):
            agent = agent()
        self.agents[agent.name] = {"agent": agent, "is_wait": is_wait}
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

    @abstractmethod
    async def execute(self, messages: Messages) -> Messages:
        """执行agent"""
