from pydantic import BaseModel, Extra


class EncryptConfig(BaseModel, extra=Extra.ignore):
    encrypt_salt: str | None = None