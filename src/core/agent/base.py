from enum import StrEnum
from inspect import isabstract
from abc import ABC, abstractmethod
from typing import Any, Type, Union, Literal, TypeVar, ClassVar, Optional, Generator, TypedDict, cast

from src.core.llm.message import Messages
from pydantic import Field, BaseModel, ConfigDict, model_validator
from src.core.llm.typings import ChatCompletionMessage, ChatCompletionToolParam, ChatCompletionMessageToolCall

AgentRiskLevel = Literal["low", "medium", "high"]
AgentT = TypeVar("AgentT", bound="BaseAgent")


class BaseAgentConfig(BaseModel):
    """所有 Agent 运行时配置的统一基类。"""

    model_config = ConfigDict(extra="ignore")


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
    """所有可执行智能体的统一基类。

    ClassRobot 约定：只有继承 ``BaseAgent`` 或 ``BaseFunctionAgent`` 的类才
    可以被称为 Agent。Runtime 上下文、Workflow 节点、Skill 目录、Retriever
    等对象属于运行时组件，不进入 Agent 继承树。

    新增 Agent 时优先覆写类级元数据 ``agent_name``、``display_name``、
    ``capabilities`` 和 ``risk_level``，再实现 ``execute()``。系统会通过
    ``iter_agent_classes()`` 从继承树自动发现 Agent，避免在多个 list/dict
    中重复维护注册信息。
    """

    agent_name: ClassVar[str | None] = None
    """Agent 的全局唯一类型名；未显式设置时会由类名转换得到。"""

    display_name: ClassVar[str | None] = None
    """面向管理端或文档展示的名称。"""

    capabilities: ClassVar[tuple[str, ...]] = ()
    """当前 Agent 对外声明的稳定能力。"""

    risk_level: ClassVar[AgentRiskLevel] = "low"
    """当前 Agent 默认风险等级，用于后续工具调用和审批策略。"""

    config: BaseAgentConfig = Field(default_factory=BaseAgentConfig)
    agents: dict[str, AgentDict] = Field(default_factory=dict)
    status: AgentStatus = Field(default=AgentStatus.init)
    messages: Messages = Field(default_factory=Messages)
    root_agent: Optional["BaseAgent"] = None
    parent_agent: list["BaseAgent"] = Field(default_factory=list)

    class Params(BaseModel):
        """定义当前智能体可接收的工具参数结构。"""

        ...

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def config_model(cls) -> type[BaseAgentConfig]:
        """返回当前 Agent 使用的配置模型类型。"""

        config_field = cls.model_fields.get("config")
        if (
            config_field is not None
            and isinstance(config_field.annotation, type)
            and issubclass(config_field.annotation, BaseAgentConfig)
        ):
            return cast(type[BaseAgentConfig], config_field.annotation)
        return BaseAgentConfig

    @classmethod
    def config_schema(cls) -> dict[str, Any]:
        """返回当前 Agent 配置的 JSON Schema。"""

        return cls.config_model().model_json_schema()

    @classmethod
    def parameters(cls) -> dict:
        """返回当前智能体的参数模式定义。

        返回:
            dict: 可供函数调用工具注册使用的 JSON Schema。
        """
        return cls.Params.model_json_schema()

    @model_validator(mode="before")
    @classmethod
    def normalize_config_payload(cls, values: Any) -> Any:
        """把旧版散装字段迁移到显式 config 对象，保持向后兼容。"""

        if not isinstance(values, dict):
            return values

        normalized = dict(values)
        config_model = cls.config_model()
        config_fields = set(getattr(config_model, "model_fields", {}))
        legacy_config = {key: normalized.pop(key) for key in list(normalized.keys()) if key in config_fields}
        if legacy_config:
            existing = normalized.get("config")
            if isinstance(existing, dict):
                merged = dict(existing)
                merged.update(legacy_config)
                normalized["config"] = merged
            elif existing is None:
                normalized["config"] = legacy_config
            elif isinstance(existing, BaseAgentConfig):
                merged = existing.model_dump()
                merged.update(legacy_config)
                normalized["config"] = merged
        config_value = normalized.get("config")
        if isinstance(config_value, BaseAgentConfig):
            normalized["config"] = config_value.model_dump()
        return normalized

    @classmethod
    def name(cls) -> str:
        """返回 Agent 的全局唯一类型名。

        子类可以直接设置 ``agent_name``，也可以覆写本方法。未设置时会把
        类名从 ``CamelCase`` 转成 ``snake_case``，例如 ``SummaryAgent``
        会得到 ``summary_agent``。
        """

        if cls.agent_name:
            return cls.agent_name
        name = cls.__name__
        chars: list[str] = []
        for index, char in enumerate(name):
            if char.isupper() and index > 0:
                chars.append("_")
            chars.append(char.lower())
        return "".join(chars)

    @classmethod
    def description(cls) -> str:
        """返回智能体的说明文本。

        返回:
            str: 默认使用类文档字符串作为描述内容。
        """
        return cls.__doc__ or ""

    @classmethod
    def title(cls) -> str:
        """返回适合界面展示的 Agent 名称。"""

        return cls.display_name or cls.__name__

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        """返回 Agent 的标准元数据，供管理端、文档和测试统一消费。"""

        return {
            "name": cls.name(),
            "class_name": cls.__name__,
            "display_name": cls.title(),
            "description": cls.description(),
            "capabilities": list(cls.capabilities),
            "risk_level": cls.risk_level,
            "config_schema": cls.config_schema(),
        }

    @classmethod
    def as_tool(cls) -> ChatCompletionToolParam:
        """生成 OpenAI function calling 兼容的工具定义。"""

        return {
            "type": "function",
            "function": {
                "name": cls.name(),
                "description": cls.description(),
                "parameters": cls.parameters(),
            },
        }

    @classmethod
    def walk_agent_subclasses(cls) -> Generator[type["BaseAgent"], None, None]:
        """深度遍历当前基类下的所有 Agent 子类。"""

        for subclass in cls.__subclasses__():
            yield subclass
            yield from subclass.walk_agent_subclasses()

    @classmethod
    def iter_agent_classes(cls, *, include_abstract: bool = False) -> tuple[type["BaseAgent"], ...]:
        """返回通过继承树发现的 Agent 类型。

        Args:
            include_abstract: 是否包含仍带抽象方法的中间基类。

        Returns:
            tuple[type[BaseAgent], ...]: 按 Agent 名称排序后的 Agent 类集合。
        """

        classes: list[type[BaseAgent]] = []
        seen: set[type[BaseAgent]] = set()
        for agent_class in cls.walk_agent_subclasses():
            if agent_class in seen:
                continue
            seen.add(agent_class)
            if not include_abstract and isabstract(agent_class):
                continue
            classes.append(agent_class)
        return tuple(sorted(classes, key=lambda item: item.name()))

    @classmethod
    def get_agent_class(cls, agent_name: str) -> type["BaseAgent"]:
        """按 Agent 类型名查找具体实现类。

        Raises:
            KeyError: 当没有匹配的 Agent 类时抛出。
            ValueError: 当多个 Agent 类声明同名时抛出。
        """

        matched = [agent_class for agent_class in cls.iter_agent_classes() if agent_class.name() == agent_name]
        if not matched:
            raise KeyError(agent_name)
        if len(matched) > 1:
            names = ", ".join(agent_class.__name__ for agent_class in matched)
            raise ValueError(f'Agent name "{agent_name}" is duplicated by: {names}')
        return matched[0]

    @classmethod
    def create(cls: type[AgentT], agent_name: str | None = None, **kwargs: Any) -> AgentT | "BaseAgent":
        """创建 Agent 实例。

        在具体子类上调用时会直接实例化该子类；在 ``BaseAgent`` 上调用时
        必须传入 ``agent_name``，由继承树自动查找实现类。
        """

        if cls is BaseAgent:
            if not agent_name:
                raise ValueError("BaseAgent.create() requires agent_name when called on BaseAgent")
            return cls.get_agent_class(agent_name)(**kwargs)
        return cls(**kwargs)

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
        if isinstance(agent, BaseAgent):
            agent_instance = cast(BaseAgent, agent)
        else:
            agent_instance = agent()
        agent_instance.parent_agent.append(self)
        agent_instance.root_agent = self.root_agent or self
        self.agents[agent_instance.name()] = {"agent": agent_instance, "is_wait": is_wait}
        return agent_instance

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """执行当前智能体的核心逻辑。

        参数:
            args: 具体 Agent 自行定义的输入参数。
            kwargs: 具体 Agent 自行定义的关键字参数。

        返回:
            Any: 具体 Agent 自行定义的执行结果。
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
        return cls.as_tool()

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
                if getattr(tool, "type", None) != "function":
                    continue
                function_tool = cast(ChatCompletionMessageToolCall, tool)
                if function_tool.function.name == self.name():
                    yield function_tool


class BaseChoiceFunctionAgent(BaseFunctionAgent):
    """定义需要用户或模型从多个候选项中选择的函数型智能体基类。"""

    ...
