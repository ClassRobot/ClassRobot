from typing import Optional
from utils.path import template_path
from jinja2 import Environment, FileSystemLoader
from base64 import b64encode


def base64_img(data: str, type_="png") -> str:
    return f"data:image/{type_};base64,{b64encode(data.encode()).decode()}"


def create_template_env(
    dir_name: str, 
    filters: Optional[dict] = None, 
    **kwargs
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
        loader=FileSystemLoader([
            template_path / "base",
            template_path / dir_name, 
        ]),
        enable_async=True,
        **kwargs
    )
    env.filters.update(filters or {})
    return env
