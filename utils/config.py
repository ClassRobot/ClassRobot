from tarina import lang
from nonebot_plugin_alconna.model import CompConfig

lang.set("completion", "node", "")
lang.set("completion", "prompt_select", "")
comp_config = CompConfig(
    exit="退出",
    lite=False,
    hides={"exit"},
    disables={"tab", "enter"},
)
