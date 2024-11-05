from nonebot_plugin_orm import Model

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime


class User(Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Bind(Model):
    platform: Mapped[str] = mapped_column(String(32), primary_key=True)
    """平台名称"""
    platform_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    """平台 ID"""
    bind_id: Mapped[int]
    """当前绑定的账号 ID"""
    original_id: Mapped[int]
    """初始时绑定的账号 ID"""
