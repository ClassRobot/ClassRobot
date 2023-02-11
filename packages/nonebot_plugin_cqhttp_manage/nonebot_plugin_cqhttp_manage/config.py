from nonebot import get_driver
from pydantic import BaseModel
from pathlib import Path
from jinja2 import Environment, FileSystemLoader



class Config(BaseModel):
    # 机器人统一存储路径
    gocqhttp_path: str = "cqhttp"
    # 是否为shell命令
    gocqhttp_shell: bool = True
    # 命令所在路径(建议添加到环境变量中并且将shell为True)
    gocqhttp_command: str = "go-cqhttp"


config = Config(**get_driver().config.dict())


class FilePath:
    base_path = Path(__file__).parent / "website"
    staticfile = base_path / "static"
    template_path = base_path / "templates"


class RoutePath:
    host: str = "127.0.0.1"
    port: int = 8080
    base_path = "/manage"
    http: str = f"http://{host}:{port}{base_path}"
    staticfile = base_path + "/static/"
    websocket = base_path + "/wss"


cqhttp_path: Path = Path.cwd().parent / config.gocqhttp_path
env = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    loader=FileSystemLoader(FilePath.template_path),
    enable_async=True
)
env.globals["static"] = RoutePath.staticfile

