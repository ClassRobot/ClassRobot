from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from utils.models import User

from .security import decode_admin_access_token


admin_bearer = HTTPBearer(auto_error=False)


async def require_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer),
) -> User:
    """校验后台登录态并返回当前管理员用户。"""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录后台管理员账号。")

    payload = decode_admin_access_token(credentials.credentials)
    user = await User.filter(id=int(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="后台登录用户不存在。")
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前用户已不再具备管理员身份。")
    return user
