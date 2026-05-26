from typing import Any
from enum import StrEnum
from dataclasses import dataclass
from contextvars import ContextVar

from nonebot import logger
from openai import NOT_GIVEN, APIError, NotGiven, AsyncOpenAI

from .message import LLMRole, Messages
from .exceptions import LLMRequestException
from .config import LLMConfig, plugin_config
from .typings import (
    ChatCompletion,
    ChatCompletionToolParam,
    ChatCompletionMessageParam,
    ChatCompletionToolChoiceOptionParam,
)


class LLMTaskType(StrEnum):
    """定义大模型调用在业务中的任务类型。"""

    chat = "chat"
    tool = "tool"
    summary = "summary"
    extract = "extract"
    plan = "plan"
    vision = "vision"
    reply = "reply"


@dataclass(slots=True)
class LLMRequest:
    """描述一次大模型调用请求。"""

    messages: list[ChatCompletionMessageParam] | Messages | str
    tools: list[ChatCompletionToolParam] | NotGiven | None = None
    tool_choice: ChatCompletionToolChoiceOptionParam | NotGiven | None = None
    max_tokens: int = 2048
    llm_name: str | None = None
    multi_modal: bool | None = None
    temperature: float | NotGiven | None = 0.1
    task_type: LLMTaskType = LLMTaskType.chat
    exclude_llm_names: tuple[str, ...] = ()


@dataclass(slots=True)
class LLMResult:
    """描述一次大模型调用结果。"""

    llm_name: str
    model: str
    response: ChatCompletion
    task_type: LLMTaskType


class ModelRouter:
    """负责根据任务类型与能力要求挑选候选模型。"""

    def __init__(self, configs: list[LLMConfig]) -> None:
        self.configs = configs

    def select(self, request: LLMRequest) -> list[LLMConfig]:
        """根据请求约束筛选并排序候选模型。"""

        candidates: list[tuple[int, int, LLMConfig]] = []
        excluded_names = set(request.exclude_llm_names)
        for index, llm_config in enumerate(self.configs):
            if llm_config.name in excluded_names:
                continue
            if request.llm_name and llm_config.name != request.llm_name:
                continue

            if self.requires_tools(request) and not llm_config.supports_functools:
                if request.llm_name:
                    raise LLMRequestException(f'LLM "<y>{llm_config.name}</y>" not support functools')
                continue

            if request.multi_modal is True and not llm_config.multi_modal:
                if request.llm_name:
                    raise LLMRequestException(f'LLM "<y>{llm_config.name}</y>" not support multi_modal')
                continue

            score = llm_config.priority
            if request.task_type.value in llm_config.tasks:
                score += 100
            elif llm_config.tasks:
                score -= 5
            else:
                score += 5

            if request.multi_modal is True and llm_config.multi_modal:
                score += 20
            if self.requires_tools(request) and llm_config.supports_functools:
                score += 20
            if request.task_type in {LLMTaskType.summary, LLMTaskType.extract, LLMTaskType.plan, LLMTaskType.reply}:
                score += 5

            candidates.append((score, -index, llm_config))

        candidates.sort(reverse=True)
        return [candidate[-1] for candidate in candidates]

    @staticmethod
    def requires_tools(request: LLMRequest) -> bool:
        """判断本次请求是否明确需要工具能力。"""

        return request.tools not in (None, NOT_GIVEN)


class LLMGateway:
    """封装模型路由、消息适配与请求执行。"""

    def __init__(self, configs: list[LLMConfig], timeout: float) -> None:
        self.timeout = timeout
        self.router = ModelRouter(configs)
        self.clients: dict[str, AsyncOpenAI] = {}
        self._attempt_errors_var: ContextVar[list[tuple[str, str]]] = ContextVar(
            "llm_gateway_attempt_errors",
            default=[],
        )

        for llm_config in configs:
            if llm_config.name in self.clients:
                logger.opt(colors=True).warning(f'LLM <y>"{llm_config.name}"</y> client already exists')
                continue
            self.clients[llm_config.name] = llm_config.build_async_openai_client()
            logger.opt(colors=True).success(f'LLM <y>"{llm_config.name}"</y> client created')

    async def create(self, request: LLMRequest) -> LLMResult:
        """执行一次大模型请求，必要时自动回退到候选模型。"""

        last_error: Exception | None = None
        attempt_errors: list[tuple[str, str]] = []
        self._attempt_errors_var.set([])
        for llm_config in self.router.select(request):
            try:
                payload_messages = await self.build_messages(request.messages, llm_config, request.multi_modal)
                request_kwargs = self.build_request_kwargs(request, payload_messages, llm_config)
                logger.opt(colors=True).info(
                    f'LLM "<y>{llm_config.name}</y>" handling task "<m>{request.task_type.value}</m>"'
                )
                response = await self.clients[llm_config.name].chat.completions.create(**request_kwargs)
                return LLMResult(
                    llm_name=llm_config.name,
                    model=llm_config.model,
                    response=response,
                    task_type=request.task_type,
                )
            except APIError as error:
                last_error = error
                attempt_errors.append((llm_config.name, str(error)))
                self._attempt_errors_var.set(list(attempt_errors))
                logger.opt(colors=True).error(f'LLM "<y>{llm_config.name}</y>" error {error}')
            except Exception as error:  # noqa: BLE001
                last_error = error
                attempt_errors.append((llm_config.name, str(error)))
                self._attempt_errors_var.set(list(attempt_errors))
                logger.exception(error)

        if last_error is not None:
            raise LLMRequestException(f"LLM request failed: {last_error}") from last_error
        raise LLMRequestException("LLM request failed")

    def get_last_attempt_errors(self) -> list[tuple[str, str]]:
        """返回当前异步上下文中最近一次模型请求的候选失败列表。"""

        return list(self._attempt_errors_var.get([]))

    def clear_last_attempt_errors(self) -> None:
        """清空当前异步上下文中最近一次模型请求的候选失败列表。"""

        self._attempt_errors_var.set([])

    def build_request_kwargs(
        self,
        request: LLMRequest,
        payload_messages: list[ChatCompletionMessageParam],
        llm_config: LLMConfig,
    ) -> dict[str, Any]:
        """构造传给 OpenAI SDK 的请求参数。"""

        request_kwargs: dict[str, Any] = {
            "stream": False,
            "messages": payload_messages,
            "max_tokens": request.max_tokens,
            "model": llm_config.model,
            "timeout": self.timeout,
        }
        if request.tools not in (None, NOT_GIVEN):
            request_kwargs["tools"] = request.tools
        if request.tool_choice not in (None, NOT_GIVEN):
            request_kwargs["tool_choice"] = request.tool_choice
        if request.temperature not in (None, NOT_GIVEN):
            request_kwargs["temperature"] = request.temperature
        return request_kwargs

    async def build_messages(
        self,
        messages: list[ChatCompletionMessageParam] | Messages | str,
        llm_config: LLMConfig,
        multi_modal: bool | None,
    ) -> list[ChatCompletionMessageParam]:
        """将内部消息对象转换为模型接口需要的格式。"""

        if isinstance(messages, str):
            text = messages
            messages = Messages()
            messages.add_message(role=LLMRole.user, content=text)

        if isinstance(messages, Messages):
            if multi_modal is False or messages.text_only():
                return await messages.build_messages()
            if llm_config.multi_modal:
                return await messages.build_messages(True)
            raise LLMRequestException(f'LLM "<y>{llm_config.name}</y>" not support multi_modal')

        return messages


llm_gateway = LLMGateway(plugin_config.llm_configs, plugin_config.llm_timeout)
