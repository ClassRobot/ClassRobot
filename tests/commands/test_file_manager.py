from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def test_private_file_commands_keep_user_space_isolated(app, onebot, send_recorder, monkeypatch, tmp_path, models):
    import src.plugins.file_manager.services as file_services
    from src.plugins.file_manager.commands import cd_cmd, ls_cmd, mkdir_cmd, pwd_cmd, rm_cmd, touch_cmd
    from utils.storage import StorageManager

    monkeypatch.setattr(file_services, "storage_manager", StorageManager(tmp_path / "storage"))
    await models.create_user(account_id=11001, nickname="文件用户")

    async with app.test_matcher(pwd_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("pwd", user_id=11001, nickname="文件用户")
        ctx.receive_event(bot, event)
    recorder.assert_any("~")

    async with app.test_matcher(mkdir_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("mkdir documents/project", user_id=11001, nickname="文件用户", message_id=2)
        ctx.receive_event(bot, event)
    recorder.assert_any("目录创建成功", "~/documents/project")

    async with app.test_matcher(cd_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("cd documents/project", user_id=11001, nickname="文件用户", message_id=3)
        ctx.receive_event(bot, event)
    recorder.assert_any("当前路径", "~/documents/project")

    async with app.test_matcher(touch_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("touch note.txt", user_id=11001, nickname="文件用户", message_id=4)
        ctx.receive_event(bot, event)
    recorder.assert_any("文件创建成功", "~/documents/project/note.txt")

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("ls", user_id=11001, nickname="文件用户", message_id=5)
        ctx.receive_event(bot, event)
    recorder.assert_any("文件列表", "📄", "note.txt", absent=("文件 note.txt",))

    async with app.test_matcher(cd_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("cd ../../..", user_id=11001, nickname="文件用户", message_id=6)
        ctx.receive_event(bot, event)
    recorder.assert_any("当前路径", "~")

    async with app.test_matcher(rm_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("rm ../../other/home", user_id=11001, nickname="文件用户", message_id=7)
        ctx.receive_event(bot, event)
    recorder.assert_any("路径越界")


async def test_group_and_private_file_spaces_are_separated(app, onebot, send_recorder, monkeypatch, tmp_path, models):
    import src.plugins.file_manager.services as file_services
    from src.plugins.file_manager.commands import ls_cmd, mkdir_cmd
    from utils.storage import StorageManager

    monkeypatch.setattr(file_services, "storage_manager", StorageManager(tmp_path / "storage"))
    await models.create_user(account_id=11002, nickname="群文件用户")

    async with app.test_matcher(mkdir_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("mkdir documents/shared", user_id=11002, group_id=21001, nickname="群文件用户")
        ctx.receive_event(bot, event)
    recorder.assert_any("目录创建成功", "~/documents/shared")

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("ls documents", user_id=11002, group_id=21001, nickname="群文件用户", message_id=2)
        ctx.receive_event(bot, event)
    recorder.assert_any("📁", "shared/", absent=("目录 shared/",))

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("ls documents", user_id=11002, nickname="群文件用户", message_id=3)
        ctx.receive_event(bot, event)
    recorder.assert_any("目录为空", absent=("shared/",))


async def test_file_service_handlers_can_be_called_by_agent_context(loaded_plugins, tmp_path):
    import src.plugins.file_manager.services as file_services
    from src.commands import CommandExecutionContext, command_executor
    from utils.storage import StorageManager

    manager = StorageManager(tmp_path / "storage")
    file_services.storage_manager = manager

    context = CommandExecutionContext(user_id=50001, roles={"user"}, invoker="agent_workflow")

    mkdir_result = await command_executor.execute("mkdir", {"路径": "documents/agent"}, context)
    assert mkdir_result.success
    assert (manager.user_space(50001).home_dir / "documents" / "agent").is_dir()

    cd_result = await command_executor.execute("cd", {"路径": "documents/agent"}, context)
    assert cd_result.success
    assert cd_result.data["path"] == "~/documents/agent"

    pwd_result = await command_executor.execute("pwd", {}, context)
    assert pwd_result.success
    assert pwd_result.data["path"] == "~/documents/agent"
