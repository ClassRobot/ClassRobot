from nonebot import get_driver
from pydantic import Extra, BaseModel


class LLMConfig(BaseModel, extra=Extra.ignore):
    """描述大模型服务连接与调用的配置项。"""
    name: str
    key: str
    url: str
    model: str
    multi_modal: bool = False
    """是否支持多模态"""
    supports_functools: bool = False
    """是否支持functools"""


class AutoGPTConfig(BaseModel, extra=Extra.ignore):
    """描述 AutoGPT 会话与规划模块的配置项。"""
    llm_configs: list[LLMConfig] = []
    llm_timeout: float = 20

    def get_config(self, name: str) -> LLMConfig:
        """获取配置。

        参数:
            name (str): 名称。

        返回:
            LLMConfig: 返回处理结果。
        """
        for llm_config in self.llm_configs:
            if llm_config.name == name:
                return llm_config
        raise Exception(f"LLM config <{name}> not found")


plugin_config = AutoGPTConfig.parse_obj(get_driver().config)
