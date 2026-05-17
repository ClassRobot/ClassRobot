import os
from pathlib import Path

import certifi
from tarina import lang
from nonebot import get_driver
from pydantic import Extra, BaseModel
from nonebot_plugin_alconna.model import CompConfig
from arclet.alconna.config import config as alc_config
from nonebot_plugin_localstore import get_data_dir, get_cache_dir, get_config_dir


class GlobalConfig(BaseModel, extra=Extra.ignore):
    """定义项目运行时使用的全局配置项。"""
    wsl_share_dir: Path | None = None
    "WSL共享目录"
    global_proxy: str | None = None
    "全局代理"
    googleapis_key: str | None = None
    "Google API Key"
    ragflow_key: str | None = None
    "Ragflow API Key"
    ragflow_url: str | None = None
    "Ragflow API URL"
    teacher_max_classes: int = 6
    "教师最大班级数量"


os.environ["SSL_CERT_FILE"] = certifi.where()
priority = 100
dirname = "classbot"
project_root = Path(__file__).resolve().parent.parent
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
    block=True,
)
alcoona_kwargs = {
    "comp_config": comp_config,
    "priority": priority,
    "skip_for_unmatch": False,
    "block": True,
}
alc_config.default_namespace.compact = True
data_dir: Path = get_data_dir(dirname)
cache_dir: Path = get_cache_dir(dirname)
config_dir: Path = get_config_dir(dirname)
resources_dir: Path = project_root / "resources"
core_dir: Path = project_root / "core"
features_dir: Path = project_root / "src" / "features"
interfaces_dir: Path = project_root / "src" / "interfaces"
agents_dir: Path = core_dir / "agent"
agent_resources_dir: Path = resources_dir / "agent"
skills_dir: Path = core_dir / "skills" / "builtin"
static_dir: Path = resources_dir
prompts_dir = resources_dir / "prompts"
template_dir = resources_dir / "templates"

agent_resources_dir.mkdir(parents=True, exist_ok=True)

temp_dir = data_dir / "temp"
temp_dir.mkdir(parents=True, exist_ok=True)

task_dir = data_dir / "tasks"
task_dir.mkdir(parents=True, exist_ok=True)

leave_dir = data_dir / "files"
leave_dir.mkdir(parents=True, exist_ok=True)

autogpt_dir = data_dir / "autogpt"
autogpt_dir.mkdir(parents=True, exist_ok=True)

storage_dir = data_dir / "storage"
storage_dir.mkdir(parents=True, exist_ok=True)

public_storage_dir = storage_dir / "public"
public_storage_dir.mkdir(parents=True, exist_ok=True)

group_storage_dir = storage_dir / "groups"
group_storage_dir.mkdir(parents=True, exist_ok=True)

user_storage_dir = storage_dir / "users"
user_storage_dir.mkdir(parents=True, exist_ok=True)
