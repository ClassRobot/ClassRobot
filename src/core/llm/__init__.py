"""ClassRobot 的核心 LLM 入口。"""

from openai import NOT_GIVEN, NotGiven

from .message import Messages
from .config import LLMConfig, AutoGPTConfig
from .gateway import LLMResult, LLMRequest, LLMTaskType, llm_gateway
from .typings import (
    ChatCompletion,
    ChatCompletionToolParam,
    ChatCompletionMessageParam,
    ChatCompletionToolChoiceOptionParam,
)


async def client_create(
    messages: list[ChatCompletionMessageParam] | Messages | str,
    functools: list[ChatCompletionToolParam] | NotGiven | None = None,
    tool_choice: ChatCompletionToolChoiceOptionParam | NotGiven | None = None,
    *,
    max_tokens: int = 2048,
    llm_name: str | None = None,
    exclude_llm_names: tuple[str, ...] | list[str] | None = None,
    multi_modal: bool | None = None,
    temperature: float | NotGiven | None = 0.1,
    task_type: LLMTaskType = LLMTaskType.chat,
) -> ChatCompletion:
    """兼容项目内旧调用习惯，并统一转发给 LLMGateway。"""

    request = LLMRequest(
        messages=messages,
        tools=functools if functools is not None else NOT_GIVEN,
        tool_choice=tool_choice if tool_choice is not None else NOT_GIVEN,
        max_tokens=max_tokens,
        llm_name=llm_name,
        exclude_llm_names=tuple(exclude_llm_names or ()),
        multi_modal=multi_modal,
        temperature=temperature if temperature is not None else NOT_GIVEN,
        task_type=task_type,
    )
    result = await llm_gateway.create(request)
    return result.response


__all__ = [
    "AutoGPTConfig",
    "ChatCompletion",
    "ChatCompletionMessageParam",
    "ChatCompletionToolChoiceOptionParam",
    "ChatCompletionToolParam",
    "LLMConfig",
    "LLMRequest",
    "LLMResult",
    "LLMTaskType",
    "Messages",
    "NOT_GIVEN",
    "NotGiven",
    "client_create",
    "llm_gateway",
]
