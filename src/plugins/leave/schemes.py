from datetime import datetime

from pydantic import BaseModel


class Leave(BaseModel):
    apply_time: datetime | None
    "请假时间"
    end_time: datetime | None
    "请假结束时间"
    reason: str | None
    "请假原因"
    is_valid: bool = False
    "请假信息是否有效"
    reply: str
    "回复用户的消息"
