from nonebot import get_driver
from openai import AsyncOpenAI

from .config import AutoGPTConfig

plugin_config = AutoGPTConfig.parse_obj(get_driver().config.dict())

client = AsyncOpenAI(
    api_key=plugin_config.auto_gpt_key, base_url=plugin_config.auto_gpt_url
)
# response = client.chat.completions.create(
#     model="deepseek-chat",
#     messages=[
#         {"role": "system", "content": prompt},
#         {"role": "user", "content": "我想知道这么创建班级"},
#     ],
#     stream=False
# )

# print(response.choices[0].message.content)
