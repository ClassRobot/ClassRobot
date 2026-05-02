import os
from pathlib import Path

import pytest
from nonebug import NONEBOT_INIT_KWARGS, NONEBOT_START_LIFESPAN


pytest_plugins = ("nonebug",)


def pytest_configure(config):
    """Configure NoneBot before nonebug initializes the test app."""

    os.environ.setdefault("ENVIRONMENT", "test")
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi+~httpx",
        "host": "127.0.0.1",
        "port": 8088,
        "env_file": ".env.test",
    }
    config.stash[NONEBOT_START_LIFESPAN] = False


def pytest_collection_modifyitems(items):
    """Keep tests predictable when they import plugin modules directly."""

    project_root = Path(__file__).resolve().parents[1]
    os.chdir(project_root)


@pytest.fixture(scope="session")
def loaded_plugins():
    """Load project plugins through NoneBot before importing plugin submodules."""

    from nonebot.plugin import load_from_toml

    return load_from_toml("pyproject.toml")
