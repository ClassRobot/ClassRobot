from utils.path import template_path
from jinja2 import Environment, FileSystemLoader


def create_template_env(dir_name: str, **kwargs) -> Environment:
    return Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        loader=FileSystemLoader([
            template_path / "base",
            template_path / dir_name, 
        ]),
        enable_async=True,
        **kwargs
    )
