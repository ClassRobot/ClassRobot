from pydantic import BaseModel, Extra


class AutoGPTConfig(BaseModel, extra=Extra.ignore):
    auto_gpt_key: str | None = None
    auto_gpt_url: str | None = None
    auto_gpt_model: str = "deepseek-chat"
