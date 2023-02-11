from typing import Any, Dict, List, Optional, Union, Generator
from fastapi.websockets import WebSocket
from datetime import datetime
from asyncio import create_task, wait, ensure_future
from pathlib import Path
from nonebot.log import logger, default_filter, default_format
from logging import StreamHandler, LogRecord
from starlette.types import Message
from psutil import Process, process_iter, cpu_percent, disk_usage, virtual_memory
from os import listdir, getpid
from asgiref.sync import sync_to_async
import yaml

from .config import cqhttp_path, config
from .typing import (
    Bot, 
    BotInfo, 
    BotFiles, 
    BaseModel, 
    BaseState,
    ClientAPI, 
    BotLogger, 
    BotConnect, 
    SystemState,
    SystemLogger, 
    )


class BotPool:
    is_change: bool = True
    
    def __init__(self) -> None:
        self.bots: Dict[str, BotInfo] = {}

    def bot_files(self) -> BotFiles:
        return BotFiles(data=[int(i) for i in listdir(cqhttp_path) if i.isdigit()])
    
    def bot_logger(self, user_id: Union[str, int], date: str = "") -> BotLogger:
        log_file = cqhttp_path / str(user_id) / "logs"
        if log_file.exists():
            date_list = listdir(log_file)
            return BotLogger(
                date_list=date_list,
                date=date or date_list[-1],
                text=(log_file / (date or date_list[-1])).read_text(encoding="utf-8")
            )
        return BotLogger(date_list=[], date="", text="")

    def bots_info(self) -> BotConnect:
        return BotConnect(data=list(self.bots.values()))
    
    async def bot_connect(self, bot: Bot) -> BotConnect:
        info = await bot.call_api("get_login_info")
        self.bots[bot.self_id] = BotInfo(
            **info,
            create_time=datetime.now().strftime(r"%Y-%m-%d %H:%M:%S")
            )
        return BotConnect(data=[info])
    
    def bot_disconnect(self, self_id: str) -> Dict[str, Any]:
        return self.bots.pop(self_id).dict()
    
    def get_bots(self) -> List[Dict[str, Any]]:
        return [bot.dict() for bot in self.bots.values()]

    def bot_exists(self, user_id: Union[str, int]) -> bool:
        return str(user_id) in self.bots


class ProcessPool:
    def __init__(self) -> None:
        self._pool: dict[str, Process] = {}
        self.process = Process(getpid())
        self.started = self.process.cpu_times()

    def get(self, user_id: str):
        return self.pool.get(user_id)

    async def system_state(self) -> SystemState:
        disk = await sync_to_async(disk_usage)("/")
        memory = await sync_to_async(virtual_memory)()
        return SystemState(
            cpu_percent=await sync_to_async(cpu_percent)(1),
            disk=BaseState(
                total=disk.total,
                used=disk.used,
                free=disk.free,
                percent=disk.percent,
                ),
            memory=BaseState(
                total=memory.total,
                used=memory.used,
                free=memory.free,
                percent=memory.percent,
            )
        )

    @property
    def pool(self) -> Dict[str, Process]:
        """机器人进程

        Returns:
            Dict[str, Process]: QQ: 进程
        """
        if not self._pool:
            self.refresh()
        return self._pool

    def is_command(self, process: Process):
        """判断是否为go-cqhttp

        Args:
            process (Process): _description_

        Returns:
            _type_: _description_
        """
        if config.gocqhttp_shell:
            return config.gocqhttp_command == process.name()
        return config.gocqhttp_command == process.cwd()

    def refresh(self):
        self._pool = {}
        for process in (i for i in process_iter() if config.gocqhttp_command in i.name()):
            config_yml = Path(process.cwd()) / "config.yml"
            if config_yml.exists():
                user_id: int = yaml.load(config_yml.read_text("utf-8"), yaml.FullLoader)["account"]["uin"]
                self._pool[str(user_id)] = process

    def kill(self, user_id: Union[str, Process]):
        if isinstance(user_id, Process):
            for i in self.pool:
                if user_id.pid == self.pool[i].pid:
                    self.pool.pop(i).kill()


class WebSocketPool:
    def __init__(self) -> None:
        self.pool: List[WebSocket] = []
        self.append = self.pool.append
        self.remove = self.pool.remove
    
    async def remove_close(self, value: WebSocket):
        """移除WebSocket并且关闭

        Args:
            value (WebSocket): WebSocket
        """
        self.remove(value)
        if value.client_state.value == 1:
            await value.close()

    async def send(self, message: Message):
        if self.pool:
            await wait(wss.send(message) for wss in self)

    async def send_text(self, data: str):
        if self.pool:
            await wait(wss.send_text(data) for wss in self)

    async def send_bytes(self, data: bytes):
        if self.pool:
            await wait(wss.send_bytes(data) for wss in self)

    async def send_json(self, data: Any, mode: str = "text"):
        data = data.dict() if isinstance(data, BaseModel) else data
        if self.pool:
            await wait([wss.send_json(data, mode) for wss in self])
    
    def __iter__(self) -> Generator[WebSocket, None, None]:
        for wss in self.pool:
            if wss.client_state.value == 1:
                yield wss
            else:
                self.remove(wss)

    def __bool__(self) -> bool:
        return bool(self.pool)


class ClientWebSocket:
    def __init__(self, wss: WebSocket) -> None:
        self.wss: WebSocket = wss
    
    async def send(self, message: Union[BaseModel, dict, str, bytes], mode: str = "text"):
        if isinstance(message, BaseModel):
            await self.wss.send_json(message.dict(), mode=mode)
        elif isinstance(message, (dict, list)):
            await self.wss.send_json(message, mode=mode)
        elif isinstance(message, str):
            await self.wss.send_text(message)
        else:
            await self.wss.send_bytes(message)
    
    def execut_api(self, api: ClientAPI):
        ...


class WebHandler(StreamHandler):
    def emit(self, record: LogRecord) -> None:
        if websocket_pool:
            create_task(websocket_pool.send_json(
                SystemLogger(data=self.format(record))
            ))


bot_pool = BotPool()
process_pool = ProcessPool()
websocket_pool = WebSocketPool()
logger.add(
    WebHandler(),
    level=0,
    enqueue=False,
    filter=default_filter,
    format=default_format,
)

  