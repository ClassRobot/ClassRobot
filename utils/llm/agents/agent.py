from __future__ import annotations

from typing import Any, cast, Callable
from dataclasses import dataclass, field

from openai import NOT_GIVEN

from utils.llm.message import LLMRole, Messages
from utils.llm.typings import ChatCompletionToolChoiceOptionParam

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


class Agent:
    """简单但可扩展的通用智能体。

    `Agent` 只负责通用编排：维护系统提示词、把工具描述交给模型、
    执行模型要求的工具调用，再把工具结果回填给模型生成最终答复。
    具体业务能力应放在工具函数里，这样调用入口能保持很短。
    """

    def __init__(
        self,
        name: str,
        *,
        instructions: str = "你是一个可靠的智能助手。",
        tools: list[AgentTool] | None = None,
        llm_name: str | None = None,
        max_steps: int = 6,
        max_tokens: int = 2048,
        temperature: float = 0.1,
    ) -> None:
        self.name = name
        self.instructions = instructions
        self.tools: list[AgentTool] = []
        self.llm_name = llm_name
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.temperature = temperature
        for agent_tool in tools or []:
            self.add_tool(agent_tool)

    def add_tool(self, agent_tool: AgentTool) -> "Agent":
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

    async def run(
        self,
        prompt: str,
        *,
        session: AgentSession | None = None,
        messages: Messages | None = None,
        tool_choice: ChatCompletionToolChoiceOptionParam | None = "auto",
    ) -> AgentResponse:
        """执行一次智能体对话。

        一次 run 可能包含多次模型请求：第一轮模型决定是否调用工具；
        如果有工具调用，执行工具并把结果作为 tool 消息追加回上下文，
        然后继续请求模型，直到模型给出自然语言结果或达到 `max_steps`。
        """

        from utils.llm import LLMTaskType, client_create

        if self.max_steps < 1:
            raise ValueError("max_steps must be greater than 0")

        working_messages = self._prepare_messages(prompt, session=session, messages=messages)
        tool_results: list[ToolCallResult] = []
        openai_tools = [tool.as_openai_tool() for tool in self.tools]
        tool_map = {tool.name: tool for tool in self.tools}
        task_type = cast(LLMTaskType, LLMTaskType.tool if openai_tools else LLMTaskType.chat)

        for _ in range(self.max_steps):
            # 将当前完整上下文交给统一 LLM 网关；网关负责模型选择与回退。
            response = await client_create(
                working_messages,
                openai_tools or NOT_GIVEN,
                tool_choice=tool_choice if openai_tools else NOT_GIVEN,
                llm_name=self.llm_name,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
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
                tool_results.append(
                    ToolCallResult(
                        name=call_name,
                        arguments=self._load_arguments(call_args),
                        result=result,
                        success=success,
                    )
                )

        content = "智能体已达到最大工具调用步数，请缩小任务范围或提高 max_steps。"
        working_messages.assistant_message(content)
        return AgentResponse(content=content, messages=working_messages, tool_calls=tool_results)

    def _prepare_messages(
        self,
        prompt: str,
        *,
        session: AgentSession | None,
        messages: Messages | None,
    ) -> Messages:
        """取得本轮可写入的消息容器，并补齐系统提示词。"""

        if messages is not None:
            working_messages = messages
        elif session is not None:
            working_messages = session.messages
        else:
            working_messages = Messages()

        # 只在空会话或缺少 system 消息时注入 instructions，避免覆盖业务侧历史。
        if not working_messages or not self._starts_with_system_message(working_messages):
            working_messages.system_message(self.instructions)
        working_messages.user_message(prompt)
        return working_messages

    @staticmethod
    def _starts_with_system_message(messages: Messages) -> bool:
        first_message = messages[0]
        return getattr(first_message, "role", None) == LLMRole.system

    @staticmethod
    def _load_arguments(arguments: str) -> dict[str, Any]:
        from utils.llm.util import json_loads

        try:
            data = json_loads(arguments)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
