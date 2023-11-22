from typing import Optional

from imgkit import from_string
from utils.sync import run_sync
from utils.config import template_path
from jinja2 import Environment, FileSystemLoader


async def html_to_image(html: str, options: Optional[dict] = None, width=600) -> bytes:
    return await run_sync(from_string)(  # type: ignore
        html,
        None,
        options={
            "width": width,
            "encoding": "UTF-8",
        }
        | (options or {}),
    )


def create_template_env(
    dir_name: str, filters: Optional[dict] = None, **kwargs
) -> Environment:
    """jinja2环境

    Args:
        dir_name (str): 所属文件夹
        filters (Optional[dict], optional): 添加函数. Defaults to None.

    Returns:
        Environment: jinja2环境
    """
    env = Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        loader=FileSystemLoader(
            [
                template_path / "base",
                template_path / dir_name,
            ]
        ),
        enable_async=True,
        **kwargs,
    )
    env.filters.update(filters or {})
    return env
