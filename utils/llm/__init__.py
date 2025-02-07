from nonebot import logger
from openai import APIError, AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from .schema import Messages
from .config import plugin_config

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
) -> ChatCompletion:
    for llm_config in plugin_config.llm_configs:
        if isinstance(messages, Messages):
            if messages.text_only():
                messages = messages.build_messages()
            elif llm_config.multi_modal:
                messages = messages.build_messages(True)
            else:
                continue
        try:
            logger.opt(colors=True).info(
                f'LLM "<y>{llm_config.name}</y>" request messages'
            )
            return await clients[llm_config.name].chat.completions.create(
                model=llm_config.model,
                stream=False,
                messages=messages,
                timeout=plugin_config.llm_timeout,
            )
        except APIError as e:
            logger.opt(colors=True).error(f'LLM "<y>{llm_config.name}</y>" error {e}')
            continue
        except Exception as e:
            logger.exception(e)
            continue
    raise Exception("LLM request failed")
