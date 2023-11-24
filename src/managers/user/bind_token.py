import json
import time

from redis import Redis
from nonebot.matcher import Matcher
from nonebot.adapters import Message
from utils.models.models import User
from utils.models.depends import get_user
from utils.auth.token import get_token_md5
from nonebot.params import Depends, CommandArg


def get_bind_token(user_id: int, ex: int = 60 * 5) -> str:
    data_dumps = json.dumps({"user_id": user_id, "time": time.time()})
    token: str = get_token_md5(data_dumps)
    with Redis(decode_responses=True) as redis:
        redis.set(token, data_dumps, ex=ex)
    return token


def get_bind_data(token: str) -> int | None:
    with Redis(decode_responses=True) as redis:
        if data := redis.get(token):
            redis.delete(token)
            return json.loads(data).get("user_id")  # type: ignore
        return None


async def bind_user(matcher: Matcher, token: Message = CommandArg()) -> User:
    if user_id := get_bind_data(token.extract_plain_text().strip()):
        if bind_user := await get_user(user_id):
            return bind_user
    await matcher.finish()


BindUser: User = Depends(bind_user)
