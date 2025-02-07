from nonebot import logger, get_driver
from openai import APIError, AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam

from .schema import Messages
from .config import AutoGPTConfig

plugin_config = AutoGPTConfig.parse_obj(get_driver().config.dict())

clients: dict[str, AsyncOpenAI] = {}

for gpt_config in plugin_config.auto_gpt:
    client = AsyncOpenAI(api_key=gpt_config.key, base_url=gpt_config.url)
    clients[gpt_config.name] = client


async def client_create(
    messages: list[ChatCompletionMessageParam] | Messages,
) -> ChatCompletion:
    for gpt_config in plugin_config.auto_gpt:
        if isinstance(messages, Messages):
            if messages.text_only():
                messages = messages.build_messages()
            elif gpt_config.multi_modal:
                messages = messages.build_messages(True)
            else:
                continue
        try:
            logger.info(f"AutoGPT {gpt_config.name} request messages")
            return await clients[gpt_config.name].chat.completions.create(
                model=gpt_config.model,
                stream=False,
                messages=messages,
                timeout=plugin_config.auto_gpt_timeout,
            )
        except APIError as e:
            logger.error(f"AutoGPT {gpt_config.name} error {e}")
            continue
        except Exception as e:
            logger.exception(e)
            continue
    raise Exception("AutoGPT error")
