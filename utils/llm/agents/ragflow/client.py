from urllib.parse import urlparse

from httpx import AsyncClient
from utils.config import global_config

version: str = "v1"


def _normalize_base_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url.rstrip("/")


ragflow_base_url = _normalize_base_url(global_config.ragflow_url)
ragflow_enabled = bool(ragflow_base_url and global_config.ragflow_key)
client_base_url = ragflow_base_url or "http://127.0.0.1"
auth_header = {"Authorization": f"Bearer {global_config.ragflow_key}"} if global_config.ragflow_key else {}

rag_client = AsyncClient(
    base_url=f"{client_base_url}/api/{version}/",
    headers=auth_header,
    timeout=60,
)
file_client = AsyncClient(
    base_url=f"{client_base_url}/{version}/",
    headers=auth_header,
    timeout=60,
)
