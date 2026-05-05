import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from nonebug import NONEBOT_INIT_KWARGS, NONEBOT_START_LIFESPAN

pytest_plugins = ("nonebug",)


def pytest_configure(config):
    """Configure NoneBot before nonebug initializes the test app."""

    os.environ["ENVIRONMENT"] = "test"
    os.environ["SESSION_EXPIRE_TIMEOUT"] = "PT90S"
    os.environ["ALEMBIC_STARTUP_CHECK"] = "false"
    os.environ.setdefault("COS_SECRET_ID", "test-secret-id")
    os.environ.setdefault("COS_SECRET_KEY", "test-secret-key")
    os.environ.setdefault("REGION", "ap-beijing")
    os.environ.setdefault("BUCKET", "test-123456")
    project_root = Path(__file__).resolve().parents[1]
    test_db_path = project_root / ".pytest_cache" / "test_dbs" / f"classbot_test_{uuid4().hex}.sqlite3"
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    # 为当前 pytest 进程分配独立 sqlite 文件，避免旧迁移状态与 Windows 文件锁污染测试。
    os.environ["SQLALCHEMY_DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path.as_posix()}"
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi+~httpx",
        "host": "127.0.0.1",
        "port": 8088,
        "env_file": ".env.test",
    }
    config.stash[NONEBOT_START_LIFESPAN] = True


def pytest_collection_modifyitems(items):
    """Keep tests predictable when they import plugin modules directly."""

    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)


def _register_test_adapters() -> None:
    """为测试环境预注册项目实际使用的 OneBot 适配器。"""

    import nonebot
    from nonebot.adapters.onebot.v11 import Adapter as OneBot11Adapter
    from nonebot.adapters.onebot.v12 import Adapter as OneBot12Adapter

    driver = nonebot.get_driver()
    registered = nonebot.get_adapters()
    for adapter in (OneBot11Adapter, OneBot12Adapter):
        if adapter.get_name() not in registered:
            driver.register_adapter(adapter)


@pytest.fixture(scope="session")
def loaded_plugins():
    """Load project plugins through NoneBot before importing plugin submodules."""

    from nonebot.plugin import load_from_toml

    # 在插件导入前先注册当前驱动可承载的适配器，避免 plugin-alconna
    # 在测试初始化早期误判“当前没有任何适配器”并输出运行时警告。
    _register_test_adapters()
    return load_from_toml("pyproject.toml")
