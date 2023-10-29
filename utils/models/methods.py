from utils.models import Bind, User
from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload
from nonebot_plugin_orm import get_session


async def get_bind_user(platform_id: int, account_id: str) -> Bind | None:
    async with get_session() as session:
        bind = await session.scalars(
            select(Bind)
            .where(Bind.platform_id == platform_id)
            .where(Bind.account_id == account_id)
            .options(
                selectinload(Bind.user).selectinload(User.teacher),
                selectinload(Bind.user).selectinload(User.student),
            )
        )
        return bind.one_or_none()
