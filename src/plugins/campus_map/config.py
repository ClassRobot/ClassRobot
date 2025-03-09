from utils.config import data_dir

map_dir = data_dir / "campus_map"
map_dir.mkdir(parents=True, exist_ok=True)

map_list_path = list(map_dir.glob("*.json"))
