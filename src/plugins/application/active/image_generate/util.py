from nonebot_plugin_alconna import Text, Image
from src.core.skills import image_generation_skill


async def generate_image(items: list[Text | Image]) -> list[dict]:
    """通过统一的图片生成 skill 调用底层绘图能力。"""
    return await image_generation_skill.generate(items)
