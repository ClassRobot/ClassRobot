from functools import partial

from nonebot import get_driver
from openai import AsyncOpenAI

from .config import AutoGPTConfig

plugin_config = AutoGPTConfig.parse_obj(get_driver().config.dict())
client = AsyncOpenAI(
    api_key=plugin_config.auto_gpt_key, base_url=plugin_config.auto_gpt_url
)
client_create = partial(
    client.chat.completions.create, model=plugin_config.auto_gpt_model, stream=False
)
