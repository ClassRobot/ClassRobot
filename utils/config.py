from pathlib import Path

from tarina import lang
from nonebot import get_driver
from pydantic import Extra, BaseModel
from nonebot_plugin_alconna.model import CompConfig
from arclet.alconna.config import config as alc_config
from nonebot_plugin_localstore import get_data_dir, get_cache_dir, get_config_dir


class GlobalConfig(BaseModel, extra=Extra.ignore):
    wsl_share_dir: Path | None = None
    "WSL共享目录"


dirname = "classbot"
# lang.set("completion", "node", "")
# lang.set("completion", "prompt_select", "")
lang.load_data(
    lang.current,
    {
        "completion": {
            "node": "",
            "prompt_select": "",
            "prompt_other": "",
            "prompt_arg": "{prompt}",
        }
    },
)
global_config = GlobalConfig.parse_obj(get_driver().config)
comp_config = CompConfig(
    exit="退出",
    lite=False,
    hides={"exit"},
    disables={"tab", "enter"},
)
alc_config.default_namespace.compact = True
data_dir: Path = get_data_dir(dirname)
cache_dir: Path = get_cache_dir(dirname)
config_dir: Path = get_config_dir(dirname)
priority = 100

task_dir = data_dir / "tasks"
task_dir.mkdir(parents=True, exist_ok=True)
