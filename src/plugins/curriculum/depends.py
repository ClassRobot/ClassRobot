from typing import Annotated

from nonebot.params import Depends
from nonebot_plugin_alconna import AlconnaMatcher
from utils.models.annotated import UserOrCreatedDepends

from .manager import AddCurriculum, QueryCurriculum, DeleteCurriculum


async def add_curriculum_depends(
    matcher: AlconnaMatcher, user: UserOrCreatedDepends
) -> AddCurriculum:
    return matcher.state.setdefault("_add_curriculum", AddCurriculum(user))


AddCurriculumDepends = Annotated[AddCurriculum, Depends(add_curriculum_depends)]


async def query_curriculum_depends(
    matcher: AlconnaMatcher, user: UserOrCreatedDepends
) -> QueryCurriculum:
    return matcher.state.setdefault("_query_curriculum", QueryCurriculum(user))


QueryCurriculumDepends = Annotated[QueryCurriculum, Depends(query_curriculum_depends)]


async def delete_curriculum_depends(
    matcher: AlconnaMatcher, user: UserOrCreatedDepends
) -> DeleteCurriculum:
    return matcher.state.setdefault("_delete_curriculum", DeleteCurriculum(user))


DeleteCurriculumDepends = Annotated[
    DeleteCurriculum, Depends(delete_curriculum_depends)
]
