from pathlib import Path

from src.platform.config import static_dir, template_dir
from nonebot_plugin_htmlrender import template_to_pic as template_to_pic_render


def static(file_path: str | Path) -> str:
    """获取静态文件的绝对路径"""
    file = str(static_dir / file_path) if isinstance(file_path, str) else str(file_path)
    return file


async def template_to_pic(file_path: str | Path, params: dict | None = None, width: int = 100, **kwargs) -> bytes:
    """将模板渲染为图片。"""
    if isinstance(file_path, str):
        file_path = template_dir / file_path
    pic = await template_to_pic_render(
        pages={
            "viewport": {"width": width, "height": 10},
        },
        template_path=str(file_path.parent),
        template_name=file_path.name,
        templates=(
            (params or {})
            | {
                "static": static,
            }
        ),
        **kwargs,
    )
    return pic
