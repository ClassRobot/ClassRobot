from pprint import pprint

from nonebot import logger
from openai import NOT_GIVEN, APIError, NotGiven, AsyncOpenAI

from .schema import Messages
from .excepions import LLMRequestException
from .config import LLMConfig, plugin_config
from .typings import ChatCompletion, ChatCompletionToolParam, ChatCompletionMessageParam

clients: dict[str, AsyncOpenAI] = {}

for llm_config in plugin_config.llm_configs:
    if llm_config.name in clients:
        logger.opt(colors=True).warning(
            f'LLM <y>"{llm_config.name}"</y> client already exists'
        )
        continue
    client = AsyncOpenAI(api_key=llm_config.key, base_url=llm_config.url)
    clients[llm_config.name] = client
    logger.opt(colors=True).success(f'LLM <y>"{llm_config.name}"</y> client created')


async def client_create(
    messages: list[ChatCompletionMessageParam] | Messages,
    tools: list[ChatCompletionToolParam] | NotGiven | None = None,
    llm_name: str | None = None,
) -> ChatCompletion:
    if tools is None:
        tools = NOT_GIVEN
    for llm_config in plugin_config.llm_configs:
        if llm_name and llm_name != llm_config.name:
            continue
        if isinstance(messages, Messages):
            if messages.text_only():
                messages = messages.build_messages()
            elif llm_config.multi_modal:
                messages = messages.build_messages(True)
            else:
                continue
            pprint(messages[1:])
        try:
            logger.opt(colors=True).info(
                f'LLM "<y>{llm_config.name}</y>" request messages'
            )
            try:
                return await clients[llm_config.name].chat.completions.create(
                    tools=tools,
                    stream=False,
                    max_tokens=2000,
                    messages=messages,
                    model=llm_config.model,
                    timeout=plugin_config.llm_timeout,
                    response_format={"type": "json_object"},
                )
            except APIError as e:
                if isinstance(e.body, dict) and (
                    str(e.body.get("code", "")) == str(20024)
                ):
                    logger.opt(colors=True).warning(
                        f'Reload LLM "<y>{llm_config.name}</y>" error {e}'
                    )
                    return await clients[llm_config.name].chat.completions.create(
                        tools=tools,
                        stream=False,
                        max_tokens=2000,
                        messages=messages,
                        model=llm_config.model,
                        timeout=plugin_config.llm_timeout,
                    )
        except APIError as e:
            logger.opt(colors=True).error(f'LLM "<y>{llm_config.name}</y>" error {e}')
            continue
        except Exception as e:
            logger.exception(e)
            continue
    raise LLMRequestException("LLM request failed")
