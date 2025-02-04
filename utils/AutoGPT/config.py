from pydantic import Extra, BaseModel


class GPTConfig(BaseModel, extra=Extra.ignore):
    name: str
    key: str
    url: str
    model: str


class AutoGPTConfig(BaseModel, extra=Extra.ignore):
    auto_gpt: list[GPTConfig] = []
