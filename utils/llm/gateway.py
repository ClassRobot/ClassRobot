from dataclasses import dataclass

from nonebot import logger
from strenum import StrEnum
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
        for index, llm_config in enumerate(self.configs):
            if request.llm_name and llm_config.name != request.llm_name:
                continue

            if self._requires_tools(request) and not llm_config.supports_functools:
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
            if self._requires_tools(request) and llm_config.supports_functools:
                score += 20
            if request.task_type in {LLMTaskType.summary, LLMTaskType.extract, LLMTaskType.plan, LLMTaskType.reply}:
                score += 5

            candidates.append((score, -index, llm_config))

        candidates.sort(reverse=True)
        return [candidate[-1] for candidate in candidates]

    @staticmethod
    def _requires_tools(request: LLMRequest) -> bool:
        return request.tools not in (None, NOT_GIVEN)


class LLMGateway:
    """封装模型路由、消息适配与请求执行。"""

    def __init__(self, configs: list[LLMConfig], timeout: float) -> None:
        self.timeout = timeout
        self.router = ModelRouter(configs)
        self.clients: dict[str, AsyncOpenAI] = {}

        for llm_config in configs:
            if llm_config.name in self.clients:
                logger.opt(colors=True).warning(f'LLM <y>"{llm_config.name}"</y> client already exists')
                continue
            self.clients[llm_config.name] = AsyncOpenAI(api_key=llm_config.key, base_url=llm_config.url)
            logger.opt(colors=True).success(f'LLM <y>"{llm_config.name}"</y> client created')

    async def create(self, request: LLMRequest) -> LLMResult:
        """执行一次大模型请求，必要时自动回退到候选模型。"""
        last_error: Exception | None = None
        for llm_config in self.router.select(request):
            try:
                payload_messages = await self._build_messages(request.messages, llm_config, request.multi_modal)
                logger.opt(colors=True).info(
                    f'LLM "<y>{llm_config.name}</y>" handling task "<m>{request.task_type.value}</m>"'
                )
                response = await self.clients[llm_config.name].chat.completions.create(
                    stream=False,
                    tools=self._normalize_optional(request.tools),
                    messages=payload_messages,
                    max_tokens=request.max_tokens,
                    model=llm_config.model,
                    temperature=self._normalize_optional(request.temperature),
                    timeout=self.timeout,
                    tool_choice=self._normalize_optional(request.tool_choice),
                )
                return LLMResult(
                    llm_name=llm_config.name,
                    model=llm_config.model,
                    response=response,
                    task_type=request.task_type,
                )
            except APIError as error:
                last_error = error
                logger.opt(colors=True).error(f'LLM "<y>{llm_config.name}</y>" error {error}')
            except Exception as error:  # noqa: BLE001
                last_error = error
                logger.exception(error)

        if last_error is not None:
            raise LLMRequestException(f"LLM request failed: {last_error}") from last_error
        raise LLMRequestException("LLM request failed")

    async def _build_messages(
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

    @staticmethod
    def _normalize_optional(value: object) -> object:
        if value is None:
            return NOT_GIVEN
        return value


llm_gateway = LLMGateway(plugin_config.llm_configs, plugin_config.llm_timeout)
