from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.asyncio


async def test_cache_falls_back_to_local_sqlite_when_redis_unavailable(loaded_plugins, monkeypatch, tmp_path):
    import utils.cache as cache_module

    async def probe_failed() -> bool:
        return False

    monkeypatch.setattr(cache_module, "_probe_redis", probe_failed)
    monkeypatch.setattr(cache_module.plugin_config, "cache_backend", "auto")
    monkeypatch.setattr(cache_module.plugin_config, "cache_fallback_enabled", True)
    monkeypatch.setattr(cache_module.plugin_config, "cache_path", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(cache_module.plugin_config, "cache_local_path", None)
    cache_module._reset_runtime_state()

    cache = cache_module.get_cache()
    assert isinstance(cache, cache_module.CacheClient)
    await cache.set("bind:token", "123", ex=300)

    assert await cache.get("bind:token") == "123"
    assert await cache.ping() is True
    assert cache.redis_cache.__class__.__name__ == "RedisCache"
    assert cache.local_cache.__class__.__name__ == "LocalCache"
    assert cache_module.get_cache_backend_hint() == "local"
    assert (tmp_path / "cache.sqlite3").exists()


async def test_cache_switches_to_local_when_redis_fails_during_operation(loaded_plugins, monkeypatch, tmp_path):
    import utils.cache as cache_module
    from utils.packages.aioredis.exceptions import ConnectionError as RedisConnectionError

    async def probe_ok() -> bool:
        return True

    async def broken_set(self, key: str, value, ex=None):
        raise RedisConnectionError("redis down")

    monkeypatch.setattr(cache_module, "_probe_redis", probe_ok)
    monkeypatch.setattr(cache_module.plugin_config, "cache_backend", "auto")
    monkeypatch.setattr(cache_module.plugin_config, "cache_fallback_enabled", True)
    monkeypatch.setattr(cache_module.plugin_config, "cache_path", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(cache_module.plugin_config, "cache_local_path", None)
    monkeypatch.setattr(cache_module.RedisCache, "set", broken_set)
    cache_module._reset_runtime_state()

    cache = cache_module.get_cache()
    assert await cache.set("bind:token", "123", ex=300) is True
    assert await cache.get("bind:token") == "123"
    assert cache_module.get_cache_backend_hint() == "local"


async def test_local_cache_honors_ttl_and_delete(loaded_plugins, monkeypatch, tmp_path):
    import utils.cache as cache_module
    import utils.cache.local_cache as local_cache_module

    current = {"value": 1000.0}
    monkeypatch.setattr(cache_module.plugin_config, "cache_backend", "local")
    monkeypatch.setattr(cache_module.plugin_config, "cache_path", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(cache_module.plugin_config, "cache_local_path", None)
    monkeypatch.setattr(local_cache_module, "_now", lambda: current["value"])
    cache_module._reset_runtime_state()

    cache = cache_module.get_cache()
    await cache.set("share:id", "owner-1", ex=2)
    assert await cache.get("share:id") == "owner-1"

    current["value"] = 1003.0
    assert await cache.get("share:id") is None

    await cache.set("share:id", "owner-2", ex=30)
    assert await cache.delete("share:id") == 1
    assert await cache.get("share:id") is None


async def test_cache_convenience_wrappers_work_with_local_fallback(loaded_plugins, monkeypatch, tmp_path):
    import utils.cache as cache_module

    monkeypatch.setattr(cache_module.plugin_config, "cache_backend", "local")
    monkeypatch.setattr(cache_module.plugin_config, "cache_path", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(cache_module.plugin_config, "cache_local_path", None)
    cache_module._reset_runtime_state()

    await cache_module.set("binary:key", "value", ex=60)
    assert await cache_module.get("binary:key") == "value"
    assert await cache_module.get_and_delete("binary:key") == "value"
    assert await cache_module.get("binary:key") is None

    binary_cache = cache_module.get_cache(decode_responses=False)
    await binary_cache.set("binary:key", b"raw", ex=60)
    assert await binary_cache.get("binary:key") == b"raw"


async def test_manager_status_reports_local_cache_backend(loaded_plugins, monkeypatch, tmp_path):
    import utils.cache as cache_module
    from src.routers.managers.status import check_cache

    monkeypatch.setattr(cache_module.plugin_config, "cache_backend", "local")
    monkeypatch.setattr(cache_module.plugin_config, "cache_path", str(tmp_path / "cache.sqlite3"))
    monkeypatch.setattr(cache_module.plugin_config, "cache_local_path", None)
    cache_module._reset_runtime_state()

    payload = await check_cache()

    assert payload["status"] == "ok"
    assert payload["backend"] == "local"
    assert Path(payload["path"]) == tmp_path / "cache.sqlite3"
    assert Path(payload["local_path"]) == tmp_path / "cache.sqlite3"


async def test_cache_storage_path_keeps_legacy_cache_local_path_compatible(
    loaded_plugins, monkeypatch, tmp_path
):
    import utils.cache as cache_module

    monkeypatch.setattr(cache_module.plugin_config, "cache_backend", "local")
    monkeypatch.setattr(cache_module.plugin_config, "cache_path", None)
    monkeypatch.setattr(
        cache_module.plugin_config, "cache_local_path", str(tmp_path / "legacy-cache.sqlite3")
    )
    cache_module._reset_runtime_state()

    cache = cache_module.get_cache()
    await cache.set("legacy:key", "legacy", ex=60)

    assert cache_module.get_cache_storage_path() == tmp_path / "legacy-cache.sqlite3"
    assert await cache.get("legacy:key") == "legacy"
    assert (tmp_path / "legacy-cache.sqlite3").exists()


async def test_cache_path_takes_precedence_over_legacy_cache_local_path(
    loaded_plugins, monkeypatch, tmp_path
):
    import utils.cache as cache_module

    primary_path = tmp_path / "primary-cache.sqlite3"
    legacy_path = tmp_path / "legacy-cache.sqlite3"

    monkeypatch.setattr(cache_module.plugin_config, "cache_backend", "local")
    monkeypatch.setattr(cache_module.plugin_config, "cache_path", str(primary_path))
    monkeypatch.setattr(cache_module.plugin_config, "cache_local_path", str(legacy_path))
    cache_module._reset_runtime_state()

    cache = cache_module.get_cache()
    await cache.set("path:key", "primary", ex=60)

    assert cache_module.get_cache_storage_path() == primary_path
    assert await cache.get("path:key") == "primary"
    assert primary_path.exists()
    assert not legacy_path.exists()


async def test_local_sqlite_cache_survives_runtime_reset(loaded_plugins, monkeypatch, tmp_path):
    import utils.cache as cache_module

    storage_path = tmp_path / "persistent-cache.sqlite3"
    monkeypatch.setattr(cache_module.plugin_config, "cache_backend", "local")
    monkeypatch.setattr(cache_module.plugin_config, "cache_path", str(storage_path))
    monkeypatch.setattr(cache_module.plugin_config, "cache_local_path", None)
    cache_module._reset_runtime_state()

    first_cache = cache_module.get_cache()
    await first_cache.set("persist:key", "persisted", ex=300)
    assert await first_cache.get("persist:key") == "persisted"

    cache_module._reset_runtime_state()

    second_cache = cache_module.get_cache()
    assert await second_cache.get("persist:key") == "persisted"
    assert storage_path.exists()
