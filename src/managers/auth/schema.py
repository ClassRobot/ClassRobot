from abc import ABC, abstractmethod

from pydantic import Field, BaseModel

edu_logins: dict[str, "type[BaseEduLogin]"] = {}


class BaseEduLogin(BaseModel, ABC):
    """描述教务系统登录所需的基础字段。"""
    account: str = Field(title="账号")
    password: str = Field(title="密码")

    @classmethod
    @abstractmethod
    def school_name(cls):
        """学校名称"""
        raise NotImplementedError

    @abstractmethod
    async def login(self):
        """执行教务系统登录流程。"""
        ...
