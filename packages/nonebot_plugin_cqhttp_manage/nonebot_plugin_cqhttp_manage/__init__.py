from nonebot import get_app, get_driver
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from asyncio import create_task, get_event_loop, sleep
from json import loads

from .config import RoutePath, FilePath, env
from .pools import websocket_pool, bot_pool, process_pool
from .apis import execut_api
from .typing import (
    ClientAPI,
    BaseMessage, 
    ClientConnect,
    BotDisconnect
    )

app: FastAPI = get_app()
driver = get_driver()


app.mount(
    RoutePath.staticfile, 
    StaticFiles(
        directory=FilePath.staticfile
        ), 
    name="static"
    )


@app.get(RoutePath.base_path)
async def manage():
    return HTMLResponse(await env.get_template("index.html").render_async())


@app.websocket(RoutePath.websocket)
async def ws(websocket: WebSocket):
    try:
        websocket_pool.append(websocket)
        await websocket.accept()
        await websocket.send_json(ClientConnect(data=list(bot_pool.bots.values())).dict())
        await websocket.send_json(bot_pool.bot_files().dict())
        while True:
            data = await websocket.receive_text()
            create_task(execut_api(websocket, ClientAPI(**loads(data))))
    except WebSocketDisconnect:
        await websocket_pool.remove_close(websocket)
        logger.warning("close")


@driver.on_bot_connect
async def _(bot: Bot):
    bot_connect = await bot_pool.bot_connect(bot)
    await websocket_pool.send_json(bot_connect)


@driver.on_bot_disconnect
async def _(bot: Bot):
    await websocket_pool.send_json(
        BotDisconnect(
            data=[bot_pool.bot_disconnect(bot.self_id)]
            )
        )


@driver.on_startup
async def _():
    logger.opt(colors=True).success(f"manage website <blue>{RoutePath.http}</blue>")
    async def _():
        while True:
            if websocket_pool:
                state = await process_pool.system_state()
                await websocket_pool.send_json(state)
            else:
                await sleep(1)
    create_task(_())

@driver.on_bot_disconnect
async def _(bot: Bot):
    logger.opt(colors=True).warning(f"<y>Bot {bot.self_id}</y> closed use manager | <blue>{RoutePath.http}</blue>")
