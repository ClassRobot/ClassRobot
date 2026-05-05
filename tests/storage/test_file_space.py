from __future__ import annotations

import pytest


def test_file_space_initializes_expected_directories(loaded_plugins, tmp_path):
    from utils.storage import DEFAULT_HOME_DIRS, StorageManager

    manager = StorageManager(tmp_path / "storage")
    space = manager.user_space(10001)

    assert (tmp_path / "storage" / "public").is_dir()
    assert (tmp_path / "storage" / "groups").is_dir()
    assert (tmp_path / "storage" / "users").is_dir()
    assert space.chat_dir.is_dir()
    assert space.home_dir.is_dir()
    for dirname in DEFAULT_HOME_DIRS:
        assert (space.home_dir / dirname).is_dir()


def test_file_space_keeps_cwd_inside_home(loaded_plugins, tmp_path):
    from utils.storage import StorageManager

    space = StorageManager(tmp_path / "storage").user_space(1)
    space.mkdir("documents/project")

    assert space.cd("documents/project") == "~/documents/project"
    assert space.cd("../..") == "~"
    assert space.cd("..") == "~"
    assert space.pwd() == "~"


def test_file_space_rejects_query_and_delete_escape(loaded_plugins, tmp_path):
    from utils.storage import PathEscapeError, StorageManager

    manager = StorageManager(tmp_path / "storage")
    user_a = manager.user_space("A")
    user_b = manager.user_space("B")
    user_b.mkdir("documents/secret")

    with pytest.raises(PathEscapeError):
        user_a.list_entries("../../B/home/documents")

    with pytest.raises(PathEscapeError):
        user_a.remove("../../B/home/documents", recursive=True)

    assert (user_b.home_dir / "documents" / "secret").is_dir()


def test_file_space_file_crud_and_protected_directories(loaded_plugins, tmp_path):
    from utils.storage import FileSpaceError, StorageManager

    space = StorageManager(tmp_path / "storage").group_space(20001)

    assert space.touch("documents/readme.txt") == "~/documents/readme.txt"
    path, text, truncated = space.read_text("documents/readme.txt")
    assert path == "~/documents/readme.txt"
    assert text == ""
    assert truncated is False

    display, entries = space.list_entries("documents")
    assert display == "~/documents"
    assert [entry.name for entry in entries] == ["readme.txt"]

    with pytest.raises(FileSpaceError):
        space.remove("documents", recursive=True)

    assert space.remove("documents/readme.txt") == "~/documents/readme.txt"
    assert not (space.home_dir / "documents" / "readme.txt").exists()


@pytest.mark.asyncio
async def test_collect_upload_payloads_downloads_file_url(loaded_plugins, monkeypatch):
    from nonebot_plugin_alconna import File
    from src.plugins.file_manager import services

    async def fake_download_file(url):
        return f"downloaded:{url}".encode()

    monkeypatch.setattr(services, "download_file", fake_download_file)

    target_dir, payloads = await services.collect_upload_payloads(
        bot=object(),
        items=("documents", File(url="https://example.invalid/report.txt", name="report.txt")),
    )

    assert target_dir == "documents"
    assert len(payloads) == 1
    assert payloads[0].name == "report.txt"
    assert payloads[0].data == b"downloaded:https://example.invalid/report.txt"
