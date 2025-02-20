from typing import Annotated

from nonebot.params import Depends
from nonebot_plugin_alconna import AlconnaMatcher
from utils.models.depends import UserOrCreatedDepends

from .manager import (
    AddCurriculum,
    BaseCurriculum,
    QueryCurriculum,
    ShareCurriculum,
    DeleteCurriculum,
    SetCurriculumWeek,
)


def curriculum_depends(bc: type[BaseCurriculum]):
    async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends) -> BaseCurriculum:
        return matcher.state.setdefault(f"_{bc.__name__}", bc(user))

    return _


AddCurriculumDepends = Annotated[
    AddCurriculum, Depends(curriculum_depends(AddCurriculum))
]


QueryCurriculumDepends = Annotated[
    QueryCurriculum, Depends(curriculum_depends(QueryCurriculum))
]


DeleteCurriculumDepends = Annotated[
    DeleteCurriculum, Depends(curriculum_depends(DeleteCurriculum))
]


SetCurriculumWeekDepends = Annotated[
    SetCurriculumWeek, Depends(curriculum_depends(SetCurriculumWeek))
]


ShareCurriculumDepends = Annotated[
    ShareCurriculum, Depends(curriculum_depends(ShareCurriculum))
]
