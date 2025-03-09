from pathlib import Path

from utils.config import template_dir
from nonebot_plugin_htmlrender import template_to_pic as template_to_pic_render


async def template_to_pic(file_path: str | Path, params: dict | None = None, width: int = 100, **kwargs) -> bytes:
    if isinstance(file_path, str):
        file_path = template_dir / file_path
    pic = await template_to_pic_render(
        pages={
            "viewport": {"width": width, "height": 10},
        },
        template_path=str(file_path.parent),
        template_name=file_path.name,
        templates=params or {},
        **kwargs,
    )
    return pic
