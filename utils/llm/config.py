from nonebot import get_driver
from pydantic import Extra, BaseModel


class LLMConfig(BaseModel, extra=Extra.ignore):
    name: str
    key: str
    url: str
    model: str
    multi_modal: bool = False


class AutoGPTConfig(BaseModel, extra=Extra.ignore):
    llm_configs: list[LLMConfig] = []
    llm_timeout: float = 20


plugin_config = AutoGPTConfig.parse_obj(get_driver().config)
