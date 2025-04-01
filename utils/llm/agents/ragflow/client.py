from httpx import AsyncClient
from utils.config import global_config

version: str = "v1"

rag_client = AsyncClient(
    base_url=f"{global_config.ragflow_url}/api/{version}/",
    headers={"Authorization": f"Bearer {global_config.ragflow_key}"},
    timeout=60,
)
file_client = AsyncClient(
    base_url=f"{global_config.ragflow_url}/{version}/",
    headers={"Authorization": f"Bearer {global_config.ragflow_key}"},
    timeout=60,
)
