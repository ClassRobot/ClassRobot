from utils.config import prompts_dir
from jinja2 import Template, Environment, FileSystemLoader

env = Environment(
    loader=FileSystemLoader(prompts_dir),
    enable_async=True,
)


def get_prompts_template(name: str) -> Template:
    """获取提示词模板。"""
    return env.get_template(name)


async def get_prompts(name: str, params: dict | None = None) -> str:
    """获取提示词。"""
    template = get_prompts_template(name)
    return await template.render_async(**(params or {}))


class Prompt:
    """负责加载并渲染提示词模板。"""
    def __init__(self, name: str, params: dict | None = None) -> None:
        """初始化实例。

        参数:
            name (str): 名称。
            params (dict | None): params。
        """
        self.name = name
        self.params = params or {}
        self.template = get_prompts_template(f"{name}.jinja")
        self.prompts: dict[str, Prompt] = {name: self}

    async def render(self, params: dict | None = None) -> str:
        """处理渲染相关逻辑。

        参数:
            params (dict | None): params。

        返回:
            str: 返回字符串结果。
        """
        prompt = await self.template.render_async(**(self.params | (params or {})))
        return prompt.replace("    ", "\t").replace("，", ",").replace("。", ".").replace("？", "?").replace("！", "!")

    async def renders(self, params: dict[str, dict] | None = None) -> str:
        """批量渲染提示词内容。

        参数:
            params (dict[str, dict] | None): params。

        返回:
            str: 返回字符串结果。
        """
        params = params or {}
        return "\n".join([await v.render(params.get(k)) for k, v in self.prompts.items()])

    def __iadd__(self, other: "Prompt") -> "Prompt":
        """实现原地累加操作。

        参数:
            other ('Prompt'): other。

        返回:
            'Prompt': 返回处理结果。
        """
        self.prompts.update(other.prompts)
        return self
