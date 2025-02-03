from pydantic import Extra, BaseModel


class GPTConfig(BaseModel, extra=Extra.ignore):
    key: str
    url: str
    model: str


class AutoGPTConfig(BaseModel, extra=Extra.ignore):
    auto_gpt: list[GPTConfig] = []
    auto_gpt_key: str | None = None
    auto_gpt_url: str | None = None
    auto_gpt_model: str = "deepseek-chat"
