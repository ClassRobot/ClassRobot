from utils.config import prompts_dir
from jinja2 import Template, Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader(prompts_dir),
    enable_async=True,
)


def get_prompts_template(name: str) -> Template:
    return env.get_template(name)


async def get_prompts(name: str, params: dict | None = None) -> str:
    template = get_prompts_template(name)
    return await template.render_async(**(params or {}))


class Prompt:
    def __init__(self, name: str) -> None:
        self.name = name
        self.template = get_prompts_template(f"{name}.jinja")

    async def render(self, params: dict | None = None) -> str:
        prompt = await self.template.render_async(**(params or {}))
        return prompt.replace("    ", "\t").replace("，", ",").replace("。", ".").replace("？", "?").replace("！", "!")
