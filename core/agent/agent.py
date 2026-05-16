from __future__ import annotations

from typing import Any, Callable, cast
from dataclasses import field, dataclass

from pydantic import Field
from openai import NOT_GIVEN

from core.llm.message import Context, LLMRole, Messages
from core.llm.typings import ChatCompletionToolChoiceOptionParam

from .base import BaseAgent, BaseAgentConfig
from .schema import AgentResponse, ToolCallResult
from .tool import AgentTool, ToolHandler, ToolExecutionError


@dataclass
class AgentSession:
    """保存一个智能体的多轮对话上下文。

    调用方可以把它按用户、群聊或业务对象缓存起来；同一个 session
    传给 `Agent.run()` 时，历史消息会继续参与下一轮模型调用。
    """

    messages: Messages = field(default_factory=Messages)

    def clear(self) -> None:
        self.messages.clear()

    def char_length(self) -> int:
        """返回当前会话中用户与助手文本的大致长度。"""

        return self.messages.char_length(LLMRole.user, LLMRole.assistant)

    async def compact(self, *, max_chars: int = 16000, keep_recent: int = 6) -> bool:
        """当会话过长时压缩历史内容。

        压缩会保留 system 消息和最近若干条消息，把更早的用户/助手对话
        折叠为一条摘要，避免长会话持续占用上下文。
        """

        from core.llm import LLMTaskType, client_create

        if self.char_length() <= max_chars or len(self.messages.messages) <= keep_recent + 1:
            return False

        system_messages = self.messages.get(LLMRole.system)
        recent_messages = self.messages.messages[-keep_recent:]
        history_messages = Messages(
            messages=[
                message
                for message in self.messages.messages[:-keep_recent]
                if isinstance(message, Context) and message.role in {LLMRole.user, LLMRole.assistant}
            ]
        )
        history_messages.user_message(
            "请压缩以上对话历史，保留用户目标、已确认事实、已调用过的系统命令、待办事项和重要约束。"
        )
        response = await client_create(
            history_messages,
            max_tokens=2048,
            task_type=LLMTaskType.summary,
        )
        summary = response.choices[0].message.content or "暂无可用摘要。"

        self.messages.clear()
        self.messages.extend(system_messages)
        self.messages.assistant_message("# 会话历史压缩摘要\n" + summary)
        self.messages.extend(recent_messages)
        return True


class ToolCallingAgentConfig(BaseAgentConfig):
    """描述通用工具调用 Agent 的稳定运行参数。"""

    instructions: str = "你是一个可靠的智能助手。"
    llm_name: str | None = None
    max_steps: int = 6
    max_tokens: int = 2048
    temperature: float = 0.1
    auto_compact_chars: int | None = 16000


class ToolCallingAgent(BaseAgent):
    """标准工具调用智能体。

    这个类实现主流 Agent 的基本闭环：准备上下文、暴露工具、执行工具、
    回填 observation，再让模型生成最终回复。它继承 ``BaseAgent``，因此
    可以被统一发现和管理；业务能力仍应该放进 ``AgentTool`` 或命令适配器。
    """

    agent_name = "tool_calling_agent"
    display_name = "工具调用智能体"
    capabilities = ("tool_calling", "conversation", "history_compaction")
    risk_level = "medium"

    config: ToolCallingAgentConfig = Field(default_factory=ToolCallingAgentConfig)
    instance_name: str = "tool_calling_agent"
    tools: list[AgentTool] = Field(default_factory=list)

    def __init__(
        self,
        name: str | None = None,
        **data: Any,
    ) -> None:
        payload = dict(data)
        if name is not None and "instance_name" not in payload:
            payload["instance_name"] = name
        super().__init__(**payload)
        if not self.instance_name:
            self.instance_name = self.agent_name or self.__class__.name()

    @property
    def instructions(self) -> str:
        """返回当前 Agent 的系统提示词。"""

        return self.config.instructions

    @property
    def llm_name(self) -> str | None:
        """返回当前 Agent 绑定的模型名称。"""

        return self.config.llm_name

    @property
    def max_steps(self) -> int:
        """返回本轮任务允许的最大工具调用步数。"""

        return self.config.max_steps

    @property
    def max_tokens(self) -> int:
        """返回单次模型调用的输出上限。"""

        return self.config.max_tokens

    @property
    def temperature(self) -> float:
        """返回当前 Agent 的生成温度。"""

        return self.config.temperature

    @property
    def auto_compact_chars(self) -> int | None:
        """返回自动压缩会话历史的阈值。"""

        return self.config.auto_compact_chars

    def add_tool(self, agent_tool: AgentTool) -> "ToolCallingAgent":
        """注册一个已构造好的工具对象，并检查工具名冲突。"""

        if any(item.name == agent_tool.name for item in self.tools):
            raise ValueError(f'Agent tool "{agent_tool.name}" already registered')
        self.tools.append(agent_tool)
        return self

    def tool(
        self,
        func: ToolHandler | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> ToolHandler | Callable[[ToolHandler], ToolHandler]:
        """注册一个 Python 函数为当前智能体工具。"""

        def decorator(inner: ToolHandler) -> ToolHandler:
            self.add_tool(AgentTool.from_function(inner, name=name, description=description))
            return inner

        if func is None:
            return decorator
        return decorator(func)

    async def execute(self, messages: Messages) -> Messages:
        """按现有消息上下文执行一次工具调用闭环。

        Args:
            messages: 调用方已经准备好的会话上下文。

        Returns:
            Messages: 追加了 assistant 或 tool observation 的消息上下文。
        """

        response = await self.run("", messages=messages, append_prompt=False)
        return response.messages

    async def run(
        self,
        prompt: str,
        *,
        session: AgentSession | None = None,
        messages: Messages | None = None,
        append_prompt: bool = True,
        tool_choice: ChatCompletionToolChoiceOptionParam | None = "auto",
    ) -> AgentResponse:
        """执行一次智能体对话。

        一次 run 可能包含多次模型请求：第一轮模型决定是否调用工具；
        如果有工具调用，执行工具并把结果作为 tool 消息追加回上下文，
        然后继续请求模型，直到模型给出自然语言结果或达到 `max_steps`。
        """

        from core.llm import LLMTaskType, client_create

        if self.max_steps < 1:
            raise ValueError("max_steps must be greater than 0")

        working_messages = self.prepare_messages(
            prompt, session=session, messages=messages, append_prompt=append_prompt
        )
        if session is not None and self.auto_compact_chars is not None:
            await session.compact(max_chars=self.auto_compact_chars)
        tool_results: list[ToolCallResult] = []
        openai_tools = self.build_openai_tools()
        tool_map = self.build_tool_map()
        task_type = cast(LLMTaskType, LLMTaskType.tool if openai_tools else LLMTaskType.chat)

        for _ in range(self.max_steps):
            response = await self.run_model_step(
                working_messages,
                openai_tools=openai_tools,
                tool_choice=tool_choice,
                task_type=task_type,
            )
            assistant_message = response.choices[0].message
            tool_calls = assistant_message.tool_calls or []
            if not tool_calls:
                # 没有工具调用时，本轮智能体任务结束，保存最终回复。
                content = assistant_message.content or ""
                working_messages.assistant_message(content)
                return AgentResponse(content=content, messages=working_messages, tool_calls=tool_results)

            working_messages.add_tool(assistant_message)
            tool_results.extend(await self.execute_tool_calls(working_messages, tool_calls, tool_map))

        content = "智能体已达到最大工具调用步数，请缩小任务范围或提高 max_steps。"
        working_messages.assistant_message(content)
        return AgentResponse(content=content, messages=working_messages, tool_calls=tool_results)

    def prepare_messages(
        self,
        prompt: str,
        *,
        session: AgentSession | None,
        messages: Messages | None,
        append_prompt: bool = True,
    ) -> Messages:
        """取得本轮可写入的消息容器，并补齐系统提示词。"""

        if messages is not None:
            working_messages = messages
        elif session is not None:
            working_messages = session.messages
        else:
            working_messages = Messages()

        # 只在空会话或缺少 system 消息时注入 instructions，避免覆盖业务侧历史。
        if not working_messages or not self.starts_with_system_message(working_messages):
            working_messages.system_message(self.instructions)
        if append_prompt:
            working_messages.user_message(prompt)
        return working_messages

    @staticmethod
    def starts_with_system_message(messages: Messages) -> bool:
        """判断消息列表第一条是否为 system 消息。"""

        first_message = messages[0]
        return getattr(first_message, "role", None) == LLMRole.system

    def build_openai_tools(self) -> list:
        """返回当前 Agent 暴露给模型的工具定义。"""

        return [tool.as_openai_tool() for tool in self.tools]

    def build_tool_map(self) -> dict[str, AgentTool]:
        """按工具名构建执行索引。"""

        return {tool.name: tool for tool in self.tools}

    async def run_model_step(
        self,
        working_messages: Messages,
        *,
        openai_tools: list,
        tool_choice: ChatCompletionToolChoiceOptionParam | None,
        task_type,
    ):
        """把当前上下文发送给统一 LLM 网关。"""

        from core.llm import client_create

        return await client_create(
            working_messages,
            openai_tools or NOT_GIVEN,
            tool_choice=tool_choice if openai_tools else NOT_GIVEN,
            llm_name=self.llm_name,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            task_type=task_type,
        )

    async def execute_tool_calls(
        self,
        working_messages: Messages,
        tool_calls,
        tool_map: dict[str, AgentTool],
    ) -> list[ToolCallResult]:
        """执行模型请求的工具调用，并把 observation 写回上下文。"""

        results: list[ToolCallResult] = []
        for tool_call in tool_calls:
            # 每个 tool_call 都必须写回一条 tool 消息，否则模型无法继续推理。
            call_name = tool_call.function.name
            call_args = tool_call.function.arguments
            agent_tool = tool_map.get(call_name)
            if agent_tool is None:
                result = f"工具 {call_name} 未注册"
                success = False
            else:
                try:
                    result = await agent_tool.run(call_args)
                    success = True
                except ToolExecutionError as error:
                    result = f"工具 {call_name} 执行失败: {error}"
                    success = False
            working_messages.tool_message(tool_call.id, result)
            results.append(
                ToolCallResult(
                    name=call_name,
                    arguments=self.load_tool_arguments(call_args),
                    result=result,
                    success=success,
                )
            )
        return results

    @staticmethod
    def load_tool_arguments(arguments: str) -> dict[str, Any]:
        """把模型返回的工具参数解析成字典，解析失败时返回空对象。"""

        from core.llm.util import json_loads

        try:
            data = json_loads(arguments)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
