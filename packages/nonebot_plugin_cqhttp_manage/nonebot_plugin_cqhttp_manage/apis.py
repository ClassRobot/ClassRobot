from nonebot import get_bots
from nonebot.adapters.onebot.v11 import Bot
from typing import Dict, Callable
from base64 import b64encode
from fastapi.websockets import WebSocket


from .typing import ClientAPI, LoginQrcode, BotLogger
from .pools import websocket_pool, bot_pool
from .process import get_bot_process, kill_bot_process, login_bot
from .config import cqhttp_path
from .utils import get_qrcode

apis: Dict[str, Callable] = {}


def got_api(api: str):
    def _(func: Callable):
        apis[api] = func
    return _


async def execut_api(wss: WebSocket, api: ClientAPI):
    if func := apis.get(api.api):
        kwargs = {
            "wss": wss,
            "websocket": wss,
            "data": api.data,
        }
        await func(*(kwargs[i] for i in func.__code__.co_varnames[:func.__code__.co_argcount]))


@got_api("bot_restart")
async def _(data):
    print(data["user_id"])


@got_api("bot_stop")
async def _(data):
    # print(get_bot_process(int(data["user_id"])).name())
    kill_bot_process(int(data["user_id"]))


@got_api("login_bot")
async def _(data: dict):
    user_id = int(data["user_id"])
    if not bot_pool.bot_exists(user_id):
        if qrcode := await login_bot(
                user_id=user_id,
                password=data.get("password", "")
            ) if get_bot_process(user_id) == None else get_qrcode(  # 当机器人不存在时进行登录,如果存在,查看是否有二维码
                user_id=user_id
            ):
            await websocket_pool.send_json(
                LoginQrcode(
                    user_id=user_id,
                    qrcode=qrcode
                )
            )
    


@got_api("update_list")
async def _(wss: WebSocket):
    await wss.send_json(bot_pool.bot_files().dict())
    await wss.send_json(bot_pool.bots_info().dict())


@got_api("robot_etails")
async def _(wss: WebSocket, data: dict):
    await wss.send_json(bot_pool.bot_logger(data["user_id"]).dict())


@got_api("bot_logger")
async def _(wss: WebSocket, data: dict):
    await wss.send_json(bot_pool.bot_logger(**data).dict())
