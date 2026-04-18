from pydantic import Extra, BaseModel


class EncryptConfig(BaseModel, extra=Extra.ignore):
    """描述加密功能使用的配置项。"""
    encrypt_salt: str | None = None
