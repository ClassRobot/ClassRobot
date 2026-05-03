import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from utils.config import global_config
from utils.models import User


ADMIN_SESSION_EXPIRE_HOURS = 12


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def get_admin_session_secret() -> str:
    """返回后台登录态签名密钥。"""

    if global_config.admin_session_secret:
        return global_config.admin_session_secret
    if global_config.admin_api_token:
        return global_config.admin_api_token
    if os.getenv("ENVIRONMENT") in {"dev", "development", "test"}:
        return "classrobot-dev-admin-session-secret"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="后台管理登录态密钥未配置，请设置 ADMIN_SESSION_SECRET。",
    )


def create_admin_access_token(user: User) -> tuple[str, datetime]:
    """为管理员用户生成访问令牌。"""

    expires_at = datetime.now(UTC) + timedelta(hours=ADMIN_SESSION_EXPIRE_HOURS)
    payload = {
        "sub": user.id,
        "username": user.username,
        "is_admin": True,
        "exp": int(expires_at.timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload_segment = _urlsafe_b64encode(payload_bytes)
    signature = hmac.new(
        get_admin_session_secret().encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    token = f"{payload_segment}.{_urlsafe_b64encode(signature)}"
    return token, expires_at


def decode_admin_access_token(token: str) -> dict:
    """校验并解析管理员访问令牌。"""

    try:
        payload_segment, signature_segment = token.split(".", 1)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="后台登录态格式无效。") from error

    expected_signature = hmac.new(
        get_admin_session_secret().encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(_urlsafe_b64encode(expected_signature), signature_segment):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="后台登录态签名无效。")

    try:
        payload = json.loads(_urlsafe_b64decode(payload_segment).decode("utf-8"))
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="后台登录态载荷无效。") from error

    if int(payload.get("exp", 0)) <= int(datetime.now(UTC).timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="后台登录态已过期，请重新登录。")
    return payload


async def authenticate_admin_user(username: str, password: str) -> User:
    """校验用户名密码并确保用户具备管理员身份。"""

    user = await User.login(username, password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误。")
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员身份可以登录后台。")
    return user
