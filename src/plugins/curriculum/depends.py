from typing import Annotated

from nonebot.params import Depends
from nonebot_plugin_alconna import AlconnaMatcher
from utils.models.depends import UserOrCreatedDepends

from .manage import AddCurricula, BaseCurricula, QueryCurricula, ShareCurricula, DeleteCurricula, SetCurriculaWeek


def curricula_depends(bc: type[BaseCurricula]):
    """构建课表依赖。"""

    async def _(matcher: AlconnaMatcher, user: UserOrCreatedDepends) -> BaseCurricula:
        """处理课表依赖中的当前流程。"""
        return matcher.state.setdefault(f"_{bc.__name__}", bc(user))

    return _


AddCurriculaDepends = Annotated[AddCurricula, Depends(curricula_depends(AddCurricula))]


QueryCurriculaDepends = Annotated[QueryCurricula, Depends(curricula_depends(QueryCurricula))]


DeleteCurriculaDepends = Annotated[DeleteCurricula, Depends(curricula_depends(DeleteCurricula))]


SetCurriculaWeekDepends = Annotated[SetCurriculaWeek, Depends(curricula_depends(SetCurriculaWeek))]


ShareCurriculaDepends = Annotated[ShareCurricula, Depends(curricula_depends(ShareCurricula))]
