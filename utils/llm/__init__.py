from nonebot import logger
from openai import NOT_GIVEN, APIError, NotGiven, AsyncOpenAI

from .config import plugin_config
from .message import Role, Messages
from .excepions import LLMRequestException
from .typings import (
    ChatCompletion,
    ChatCompletionToolParam,
    ChatCompletionMessageParam,
    ChatCompletionToolChoiceOptionParam,
)

clients: dict[str, AsyncOpenAI] = {}

for llm_config in plugin_config.llm_configs:
    if llm_config.name in clients:
        logger.opt(colors=True).warning(f'LLM <y>"{llm_config.name}"</y> client already exists')
        continue
    client = AsyncOpenAI(api_key=llm_config.key, base_url=llm_config.url)
    clients[llm_config.name] = client
    logger.opt(colors=True).success(f'LLM <y>"{llm_config.name}"</y> client created')


async def client_create(
    messages: list[ChatCompletionMessageParam] | Messages | str,
    functools: list[ChatCompletionToolParam] | NotGiven | None = None,
    tool_choice: ChatCompletionToolChoiceOptionParam | NotGiven | None = None,
    *,
    max_tokens: int = 1000,
    llm_name: str | None = None,
    multi_modal: bool | None = None,
    temperature: float | NotGiven | None = None,
) -> ChatCompletion:
    """Create LLM client

    Args:
        messages (list[ChatCompletionMessageParam] | Messages): 发送的消息
        functools (list[ChatCompletionToolParam] | NotGiven | None, optional): 函数工具. Defaults to None.
        llm_name (str | None, optional): 指定特定的模型，不填写则动态切换
        multi_modal (bool | None, optional): 是否多模态消息. `None`表示动态切换,`True`表示多模态消息,`False`表示单模态消息. Defaults to None.
    """
    if functools is None:
        functools = NOT_GIVEN
    if temperature is None:
        temperature = NOT_GIVEN
    if tool_choice is None:
        tool_choice = NOT_GIVEN

    for llm_config in plugin_config.llm_configs:
        # 如果在指定了llm_name的情况下
        if llm_name:
            if llm_name != llm_config.name:
                continue
            # 查看是否传了functools,如果传了则判断是否支持函数调用，不支持则报错
            elif functools is not NOT_GIVEN and not llm_config.supports_functools:
                raise LLMRequestException(f'LLM "<y>{llm_config.name}</y>" not support functools')
            # 判断是否启用了多模态，如果启用了但不支持则报错
            elif multi_modal is True and not llm_config.multi_modal:
                raise LLMRequestException(f'LLM "<y>{llm_config.name}</y>" not support multi_modal')

        # 如果没有指定llm_name则动态切换
        # 判断是否传了functools,如果传了则判断是否支持函数调用，不支持则跳过
        if functools is not NOT_GIVEN and not llm_config.supports_functools:
            continue

        # 判断是否启用了多模态，如果启用了但不支持则跳过
        if multi_modal is True and not llm_config.multi_modal:
            continue

        if isinstance(messages, str):
            text = messages
            messages = Messages()
            messages.add_message(role=Role.user, content=text)

        if isinstance(messages, Messages):
            # 如果要求只使用单模态，或者消息只有文本
            if multi_modal is False or messages.text_only():
                messages = await messages.build_messages()
            # 如果支持多模态
            elif llm_config.multi_modal:
                messages = await messages.build_messages(True)
            else:
                continue
            # pprint(messages[1:])
        try:
            logger.opt(colors=True).info(f'LLM "<y>{llm_config.name}</y>" request messages')
            return await clients[llm_config.name].chat.completions.create(
                stream=False,
                tools=functools,
                messages=messages,
                max_tokens=max_tokens,
                model=llm_config.model,
                temperature=temperature,
                timeout=plugin_config.llm_timeout,
                tool_choice=tool_choice,
            )
        except APIError as e:
            logger.opt(colors=True).error(f'LLM "<y>{llm_config.name}</y>" error {e}')
            continue
        except Exception as e:
            logger.exception(e)
            continue
    raise LLMRequestException("LLM request failed")
