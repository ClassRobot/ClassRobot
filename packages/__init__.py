from nonebot import load_plugins
from pathlib import Path


for plugin_dir in Path(__file__).parent.iterdir():
    if plugin_dir.is_dir() and not plugin_dir.name.startswith("__"):
        load_plugins(str(plugin_dir))
