import json
import time

from redis import Redis
from utils.auth.token import get_token_md5


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
