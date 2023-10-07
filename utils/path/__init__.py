from pathlib import Path
from nonebot_plugin_localstore import get_cache_dir, get_data_dir, get_config_dir

base_path = Path.cwd()

template_path = base_path / "templates"
cache_path = get_cache_dir(None)
data_path = get_data_dir(None)
config_path = get_config_dir(None)
