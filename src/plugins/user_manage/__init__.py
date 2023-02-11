from nonebot import load_plugins
from pathlib import Path

load_plugins(str(Path(__file__).parent / "manage"))
