from abc import ABC, abstractmethod

from pydantic import Field, BaseModel

edu_logins: list["type[BaseEduLogin]"] = []


class BaseEduLogin(BaseModel, ABC):
    account: str = Field(title="账号")
    password: str = Field(title="密码")

    @classmethod
    @abstractmethod
    def school_name(cls):
        """学校名称"""
        raise NotImplementedError

    @abstractmethod
    async def login(self):
        ...
