from pydantic import Extra, BaseModel


class EncryptConfig(BaseModel, extra=Extra.ignore):
    encrypt_salt: str | None = None
