from nonebot import logger, get_driver
from openai import APIError, AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from .config import AutoGPTConfig

plugin_config = AutoGPTConfig.parse_obj(get_driver().config.dict())

clients: dict[str, AsyncOpenAI] = {}

for gpt_config in plugin_config.auto_gpt:
    client = AsyncOpenAI(api_key=gpt_config.key, base_url=gpt_config.url)
    clients[gpt_config.name] = client


async def client_create(messages: list[ChatCompletionMessageParam]) -> ChatCompletion:
    for gpt_config in plugin_config.auto_gpt:
        try:
            return await clients[gpt_config.name].chat.completions.create(
                model=gpt_config.model, stream=False, messages=messages
            )
        except APIError as e:
            logger.error(f"AutoGPT {gpt_config.name} error {e}")
            continue
    raise Exception("AutoGPT error")
