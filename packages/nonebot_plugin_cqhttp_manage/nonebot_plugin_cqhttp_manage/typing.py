from pydantic import BaseModel
from typing import Union, List, Optional
from nonebot.adapters import onebot
from psutil import Process

Bot = Union[onebot.v11.Bot, onebot.v12.Bot]


class BaseMessage(BaseModel):
    # data: Union[str, dict, list]
    type: str = "BaseMessage"
    state: int = 200


class ClientConnect(BaseMessage):
    """客户端连接时触发"""
    type: str = "ClientConnect"
    data: list


class BotConnect(BaseMessage):
    """机器人连接时触发"""
    type: str = "BotConnect"
    data: list


class BotDisconnect(BaseMessage):
    """机器人断开时触发"""
    type: str = "BotDisconnect"
    data: List[dict]


class BotFiles(BaseMessage):
    """cqhttp文件夹下的机器人列表"""
    type: str = "BotFiles"
    data: List[int]


class LoginQrcode(BaseMessage):
    """登录二维码"""
    type: str = "LoginQrcode"
    user_id: int
    qrcode: str


class BotLogger(BaseMessage):
    type: str = "BotLogger"
    date_list: List[str]
    date: str
    text: str


class SystemLogger(BaseMessage):
    type: str = "SystemLogger"
    data: str


class BotInfo(BaseModel):
    """机器人信息"""
    user_id: int
    nickname: str
    create_time: str


class BaseState(BaseModel):
    total: int
    used: int
    free: int
    percent: float


class SystemState(BaseMessage):
    type: str = "SystemState"
    cpu_percent: float
    disk: BaseState
    memory: BaseState


# 客户端消息
class ClientAPI(BaseModel):
    """客户端发送的api"""
    api: str
    data: Optional[Union[dict, list, str]] = None


class GoCqhttpProcess(BaseModel):
    user_id: str
    cwd: str
    pid: int