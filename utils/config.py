from nonebot_plugin_alconna.model import CompConfig
from tarina import lang

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

priority = 100
