from typing import Annotated

from nonebot.params import Depends
from nonebot.matcher import Matcher


async def validate_name_not_numeric(matcher: Matcher, validate_name: str) -> str:
    if not validate_name.isdigit():
        return validate_name
    await matcher.finish("名称不能为纯数字！")


ValidateNameNotNumeric = Annotated[str, Depends(validate_name_not_numeric)]
