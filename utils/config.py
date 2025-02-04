from tarina import lang
from nonebot_plugin_alconna.model import CompConfig
from arclet.alconna.config import config as alc_config
from nonebot_plugin_localstore import get_data_dir, get_cache_dir, get_config_dir

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
comp_config = CompConfig(
    exit="退出",
    lite=False,
    hides={"exit"},
    disables={"tab", "enter"},
)
alc_config.default_namespace.compact = True
data_dir = get_data_dir(dirname)
cache_dir = get_cache_dir(dirname)
config_dir = get_config_dir(dirname)
priority = 100
