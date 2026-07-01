from __future__ import annotations

from fastapi import Depends, APIRouter

from .. import audit
from ..schemas import LoginRequest, TokenResponse
from ..security import SESSION_TTL_SECONDS, token_store, manager_auth, manager_auth_token

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    """使用启动令牌登录本地管理后台。

    Args:
        payload: 登录请求体，包含启动令牌。

    Returns:
        TokenResponse: 新创建的 bearer 会话令牌。
    """

    session_token, _ = token_store.login(payload.token)
    audit.log_event("auth", "login", "completed")
    return TokenResponse(access_token=session_token, expires_in=SESSION_TTL_SECONDS)


@router.get("/auth/me")
async def auth_me(session=Depends(manager_auth)):
    """返回当前管理端会话信息。"""

    return {
        "authenticated": True,
        "role": "local_manager",
        "issued_at": session.issued_at,
        "expires_at": session.expires_at,
    }


@router.post("/auth/logout")
async def logout(session_token: str = Depends(manager_auth_token)):
    """注销当前管理端会话。

    Args:
        session_token: 当前 bearer token。

    Returns:
        dict[str, bool]: 注销结果。
    """

    token_store.logout(session_token)
    audit.log_event("auth", "logout", "completed")
    return {"logged_out": True}
