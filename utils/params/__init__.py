from nonebot.params import Depends
from nonebot.typing import T_State
from nonebot.matcher import Matcher
from nonebot.adapters import Message

from utils.tools.docs_sheet import re_docs


async def docs_url_depends(state: T_State, matcher: Matcher) -> str:
    for value in state.values():
        if isinstance(value, Message):
            if url := re_docs(str(value)):
                return url
    await matcher.finish()


DocsUrlParams = Depends(docs_url_depends)


