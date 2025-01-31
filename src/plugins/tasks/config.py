from pathlib import Path

from utils.config import data_dir

task_dir: Path = data_dir / "tasks"
task_dir.mkdir(parents=True, exist_ok=True)
