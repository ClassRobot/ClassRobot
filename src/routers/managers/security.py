from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from secrets import compare_digest, token_urlsafe

from nonebot import logger
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


SESSION_TTL_SECONDS = 24 * 60 * 60


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class ManagerSession:
    token_hash: str
    issued_at: datetime
    expires_at: datetime


class ManagerTokenStore:
    """In-memory token store for the local manager console."""

    def __init__(self) -> None:
        self._startup_token = ""
        self._startup_token_hash = ""
        self._sessions: dict[str, ManagerSession] = {}
        self.rotate_startup_token(log_token=True)

    def rotate_startup_token(self, *, log_token: bool = False) -> str:
        self._startup_token = token_urlsafe(32)
        self._startup_token_hash = _hash_token(self._startup_token)
        self._sessions.clear()
        if log_token:
            logger.opt(colors=True).warning(
                "ClassRobot manager login token: <y>{}</y>",
                self._startup_token,
            )
        return self._startup_token

    def preview_startup_token(self) -> str:
        if len(self._startup_token) <= 8:
            return "***"
        return f"{self._startup_token[:4]}****{self._startup_token[-4:]}"

    def login(self, token: str) -> tuple[str, ManagerSession]:
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
        session = self._sessions.get(token)
        if session is None or not compare_digest(_hash_token(token), session.token_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid manager session")
        if session.expires_at < datetime.now():
            self._sessions.pop(token, None)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Manager session expired")
        return session

    def logout(self, token: str) -> None:
        self._sessions.pop(token, None)


token_store = ManagerTokenStore()
bearer_scheme = HTTPBearer(auto_error=False)


async def manager_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> ManagerSession:
    """FastAPI dependency requiring a valid manager bearer token."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing manager session")
    return token_store.validate_session(credentials.credentials)


async def manager_auth_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing manager session")
    token_store.validate_session(credentials.credentials)
    return credentials.credentials
