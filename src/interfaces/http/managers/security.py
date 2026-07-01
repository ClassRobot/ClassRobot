from __future__ import annotations

from hashlib import sha256
from dataclasses import dataclass
from datetime import datetime, timedelta
from secrets import token_urlsafe, compare_digest

from nonebot import logger
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SESSION_TTL_SECONDS = 24 * 60 * 60


def _hash_token(token: str) -> str:
    """计算令牌的 SHA-256 摘要。

    Args:
        token: 原始启动令牌或会话令牌。

    Returns:
        str: 令牌哈希值。
    """
    return sha256(token.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ManagerSession:
    """管理端会话信息。"""

    token_hash: str
    issued_at: datetime
    expires_at: datetime


class ManagerTokenStore:
    """本地管理后台使用的内存令牌存储。"""

    def __init__(self) -> None:
        """初始化启动令牌和会话缓存。"""
        self._startup_token = ""
        self._startup_token_hash = ""
        self._sessions: dict[str, ManagerSession] = {}
        self.rotate_startup_token(log_token=True)

    def rotate_startup_token(self, *, log_token: bool = False) -> str:
        """重置启动令牌并清空现有会话。

        Args:
            log_token: 是否把新令牌打印到应用日志中。

        Returns:
            str: 新生成的启动令牌。
        """
        self._startup_token = token_urlsafe(32)
        self._startup_token_hash = _hash_token(self._startup_token)
        self._sessions.clear()
        if log_token:
            logger.opt(colors=True).warning(
                "ClassRobot 管理后台登录令牌：<y>{}</y>",
                self._startup_token,
            )
        return self._startup_token

    def preview_startup_token(self) -> str:
        """返回脱敏后的启动令牌预览。

        Returns:
        str: 适合展示在后台提示中的令牌预览文本。
        """
        if len(self._startup_token) <= 8:
            return "***"
        return f"{self._startup_token[:4]}****{self._startup_token[-4:]}"

    def login(self, token: str) -> tuple[str, ManagerSession]:
        """校验启动令牌并创建会话。

        Args:
            token: 登录页提交的启动令牌。

        Returns:
            tuple[str, ManagerSession]: 原始会话令牌与对应会话对象。

        Raises:
            HTTPException: 当启动令牌无效时抛出 401。
        """
        if not compare_digest(_hash_token(token), self._startup_token_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid manager token")

        session_token = token_urlsafe(32)
        now = datetime.now()
        session = ManagerSession(
            token_hash=_hash_token(session_token),
            issued_at=now,
            expires_at=now + timedelta(seconds=SESSION_TTL_SECONDS),
        )
        self._sessions[session_token] = session
        return session_token, session

    def validate_session(self, token: str) -> ManagerSession:
        """校验访问会话。

        Args:
            token: 请求头中的访问令牌。

        Returns:
            ManagerSession: 已通过校验的会话对象。

        Raises:
            HTTPException: 当会话不存在、校验失败或已过期时抛出 401。
        """
        session = self._sessions.get(token)
        if session is None or not compare_digest(_hash_token(token), session.token_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid manager session")
        if session.expires_at < datetime.now():
            self._sessions.pop(token, None)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Manager session expired")
        return session

    def logout(self, token: str) -> None:
        """注销一个会话。

        Args:
            token: 需要移除的原始 session token。
        """
        self._sessions.pop(token, None)


token_store = ManagerTokenStore()
bearer_scheme = HTTPBearer(auto_error=False)


async def manager_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ManagerSession:
    """验证管理端访问会话并返回会话对象。

    Args:
        credentials: FastAPI 注入的认证请求头对象。

    Returns:
        ManagerSession: 已通过验证的会话对象。

    Raises:
        HTTPException: 当缺少认证信息或访问令牌无效时抛出 401。
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing manager session")
    return token_store.validate_session(credentials.credentials)


async def manager_auth_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """验证管理端访问会话并返回原始令牌。

    Args:
        credentials: FastAPI 注入的认证请求头对象。

    Returns:
        str: 已通过验证的原始访问令牌。

    Raises:
        HTTPException: 当缺少认证信息或访问令牌无效时抛出 401。
    """

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing manager session")
    token_store.validate_session(credentials.credentials)
    return credentials.credentials
