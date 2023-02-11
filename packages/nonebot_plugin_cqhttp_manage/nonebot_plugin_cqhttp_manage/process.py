from os import listdir
from pathlib import Path
from asyncio import sleep
from typing import List, Optional, Union
from psutil import Process, NoSuchProcess
import subprocess

from .config import cqhttp_path, FilePath, config
from .utils import get_qrcode

base_config_file = FilePath.staticfile / "config.yml"


async def login_bot(user_id: int, password: str = "") -> Optional[str]:
    """登录机器人

    Args:
        user_id (int): 用户qq号
        password (str, optional): 密码. Defaults to "".

    Returns:
        Optional[str]: 登录后如果存在二维码则生成二维码
    """
    bot_file = cqhttp_path / str(user_id)
    bot_file.mkdir(parents=True, exist_ok=True)
    config_file = bot_file / "config.yml"
    # 如果没用config.yml就生成一个
    if not config_file.exists():
        config_file.write_text(
            base_config_file.read_text("utf-8").format(
                user_id=user_id,
                password=password), 
            "utf-8")
    # 获取登录二维码
    qrcode_file = bot_file / "qrcode.png"
    qrcode_file.unlink(True)
    subprocess.run((config.gocqhttp_command, "-d", "-faststart"), shell=config.gocqhttp_shell, cwd=bot_file)
    for _ in range(60):
        await sleep(1)
        if qrcode := get_qrcode(qrcode_file):
            return qrcode


def cqhttp_bots() -> List[str]:
    return listdir(cqhttp_path)


def get_bot_process(user_id: int) -> Optional[Process]:
    bot_file = cqhttp_path / str(user_id)
    pid_file = bot_file / "go-cqhttp.pid"
    if bot_file.exists() and pid_file.exists():
        pid = pid_file.read_text()
        if pid.isdigit():
            try:
                return Process(int(pid))
            except NoSuchProcess:
                pid_file.unlink()


def kill_bot_process(user_id: Union[int, Process]) -> bool:
    if process := user_id if isinstance(user_id, Process) else get_bot_process(user_id):
        process.kill()
        return True
    return False
