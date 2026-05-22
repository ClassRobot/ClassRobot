from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_private_file_commands_keep_user_space_isolated(
    app, onebot, send_recorder, monkeypatch, tmp_path, models
):
    import src.plugins.application.active.file_manager.services as file_services
    from src.plugins.application.active.file_manager.commands import (
        cd_cmd,
        find_cmd,
        grep_cmd,
        ls_cmd,
        mkdir_cmd,
        pwd_cmd,
        rm_cmd,
        touch_cmd,
        tree_cmd,
    )
    from src.core.storage import StorageManager

    monkeypatch.setattr(file_services, "storage_manager", StorageManager(tmp_path / "storage"))
    user = await models.create_user(account_id=11001, nickname="文件用户")

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

    note_path = file_services.storage_manager.user_space(user.id).home_dir / "documents" / "project" / "note.txt"
    note_path.write_text("班会材料：周五下午三点开会。\n带上作业统计。", encoding="utf-8")

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("ls", user_id=11001, nickname="文件用户", message_id=5)
        ctx.receive_event(bot, event)
    recorder.assert_any("文件列表", "📄", "note.txt", absent=("文件 note.txt", "0B", "KB", "MB"))

    async with app.test_matcher(find_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("find note ~/documents", user_id=11001, nickname="文件用户", message_id=50)
        ctx.receive_event(bot, event)
    recorder.assert_any("查找文件", "~/documents/project/note.txt")

    async with app.test_matcher(grep_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("grep 班会 ~/documents", user_id=11001, nickname="文件用户", message_id=51)
        ctx.receive_event(bot, event)
    recorder.assert_any("内容搜索", "~/documents/project/note.txt:1", "班会材料")

    async with app.test_matcher(tree_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("tree ~/documents 2", user_id=11001, nickname="文件用户", message_id=52)
        ctx.receive_event(bot, event)
    recorder.assert_any("文件树", "📁 project/", "📄 note.txt")

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

    async with app.test_matcher(find_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("find note ../../other", user_id=11001, nickname="文件用户", message_id=8)
        ctx.receive_event(bot, event)
    recorder.assert_any("路径越界")


async def test_file_manager_rejects_reserved_mount_directory_names(
    app, onebot, send_recorder, monkeypatch, tmp_path, models
):
    import src.plugins.application.active.file_manager.services as file_services
    from src.plugins.application.active.file_manager.commands import mkdir_cmd
    from src.core.storage import StorageManager

    monkeypatch.setattr(file_services, "storage_manager", StorageManager(tmp_path / "storage"))
    user = await models.create_user(account_id=11009, nickname="保留目录用户")

    for index, dirname in enumerate(("群组", "班级", "学院", "学校"), start=1):
        async with app.test_matcher(mkdir_cmd) as ctx:
            recorder = send_recorder(ctx)
            bot = onebot.create_bot(ctx)
            event = onebot.private_event(
                f"mkdir {dirname}",
                user_id=11009,
                nickname="保留目录用户",
                message_id=90 + index,
            )
            ctx.receive_event(bot, event)
        recorder.assert_any("保留目录名", "不能创建同名目录")
        assert not (file_services.storage_manager.user_space(user.id).home_dir / dirname).exists()


async def test_group_context_mounts_system_group_but_defaults_to_user_space(
    app, onebot, send_recorder, monkeypatch, tmp_path, models
):
    import src.plugins.application.active.file_manager.services as file_services
    from src.plugins.application.active.file_manager.commands import ls_cmd, mkdir_cmd
    from tests.commands.conftest import PLATFORM_ID
    from src.models import GroupBind
    from src.core.storage import StorageManager

    monkeypatch.setattr(file_services, "storage_manager", StorageManager(tmp_path / "storage"))
    user = await models.create_user(account_id=11002, nickname="群文件用户")

    async with app.test_matcher(mkdir_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("mkdir documents/shared", user_id=11002, group_id=21001, nickname="群文件用户")
        ctx.receive_event(bot, event)
    recorder.assert_any("目录创建成功", "~/documents/shared")

    group_bind = await GroupBind.get_bind(PLATFORM_ID, "21001", None)
    assert group_bind is not None
    assert (file_services.storage_manager.user_space(user.id).home_dir / "documents" / "shared").is_dir()
    assert not (
        file_services.storage_manager.group_space(group_bind.group_id).home_dir / "documents" / "shared"
    ).exists()

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("ls documents", user_id=11002, nickname="群文件用户", message_id=2)
        ctx.receive_event(bot, event)
    recorder.assert_any("📁", "shared/", absent=("目录 shared/",))

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("ls", user_id=11002, group_id=21001, nickname="群文件用户", message_id=3)
        ctx.receive_event(bot, event)
    recorder.assert_any("群组/", "群组文件", "documents/")

    async with app.test_matcher(mkdir_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event(
            f"mkdir 群组/{group_bind.group_id}/documents/shared-group",
            user_id=11002,
            group_id=21001,
            nickname="群文件用户",
            message_id=4,
        )
        ctx.receive_event(bot, event)
    recorder.assert_any("目录创建成功", f"~/群组/{group_bind.group_id}/documents/shared-group")

    assert (
        file_services.storage_manager.group_space(group_bind.group_id).home_dir / "documents" / "shared-group"
    ).is_dir()
    assert not file_services.storage_manager.space_root("group", "21001").exists()


async def test_student_file_scope_mounts_class_college_and_school_readonly(
    app, onebot, send_recorder, monkeypatch, tmp_path, models
):
    import src.plugins.application.active.file_manager.services as file_services
    from src.plugins.application.active.file_manager.commands import find_cmd, grep_cmd, ls_cmd, mkdir_cmd
    from src.core.storage import StorageManager

    monkeypatch.setattr(file_services, "storage_manager", StorageManager(tmp_path / "storage"))

    owner = await models.create_user(account_id=11003, nickname="班级创建者")
    school = await models.create_school("文件学校")
    college = await models.create_college(school, name="文件学院")
    major = await models.create_major(school, college, name="文件专业")
    classes = await models.create_classes(
        name="文件班级",
        owner=owner,
        group_id=21003,
        school=school,
        college=college,
        major=major,
    )
    student_user = await models.create_user(account_id=11004, nickname="文件学生")
    await models.create_student(student_user, classes=classes, school=school)

    class_note = file_services.storage_manager.class_space(classes.id).home_dir / "documents" / "class-note.txt"
    class_note.write_text("班级资料：下周提交实践报告。", encoding="utf-8")
    college_note = file_services.storage_manager.college_space(college.id).home_dir / "documents" / "college.txt"
    college_note.write_text("学院资料：创新项目报名。", encoding="utf-8")
    school_note = file_services.storage_manager.school_space(school.id).home_dir / "documents" / "school.txt"
    school_note.write_text("学校资料：校历已经发布。", encoding="utf-8")

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("ls", user_id=11004, nickname="文件学生")
        ctx.receive_event(bot, event)
    recorder.assert_any("班级/", "学院/", "学校/", "只读")

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"ls 班级/{classes.id}/documents", user_id=11004, nickname="文件学生", message_id=2
        )
        ctx.receive_event(bot, event)
    recorder.assert_any("class-note.txt")

    async with app.test_matcher(find_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("find class-note", user_id=11004, nickname="文件学生", message_id=3)
        ctx.receive_event(bot, event)
    recorder.assert_any("查找文件", f"~/班级/{classes.id}/documents/class-note.txt")

    async with app.test_matcher(grep_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"grep 创新 学院/{college.id}",
            user_id=11004,
            nickname="文件学生",
            message_id=4,
        )
        ctx.receive_event(bot, event)
    recorder.assert_any("内容搜索", f"~/学院/{college.id}/documents/college.txt:1", "创新项目")

    async with app.test_matcher(mkdir_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"mkdir 班级/{classes.id}/documents/student-write",
            user_id=11004,
            nickname="文件学生",
            message_id=5,
        )
        ctx.receive_event(bot, event)
    recorder.assert_any("没有写入权限", "文件班级")


async def test_teacher_can_write_class_mounted_space(app, onebot, send_recorder, monkeypatch, tmp_path, models):
    import src.plugins.application.active.file_manager.services as file_services
    from src.plugins.application.active.file_manager.commands import mkdir_cmd
    from src.core.storage import StorageManager

    monkeypatch.setattr(file_services, "storage_manager", StorageManager(tmp_path / "storage"))

    teacher_user = await models.create_user(account_id=11005, nickname="文件教师")
    teacher = await models.create_teacher(teacher_user, name="文件教师")
    classes = await models.create_classes(name="教师文件班", owner=teacher_user, group_id=21005, teacher=teacher)

    async with app.test_matcher(mkdir_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            f"mkdir 班级/{classes.id}/documents/teacher-write",
            user_id=11005,
            nickname="文件教师",
        )
        ctx.receive_event(bot, event)
    recorder.assert_any("目录创建成功", f"~/班级/{classes.id}/documents/teacher-write")
    assert (file_services.storage_manager.class_space(classes.id).home_dir / "documents" / "teacher-write").is_dir()


async def test_file_service_handlers_can_be_called_by_agent_context(loaded_plugins, tmp_path):
    import src.plugins.application.active.file_manager.services as file_services
    from src.platform.commands import CommandExecutionContext, command_executor
    from src.core.storage import StorageManager

    manager = StorageManager(tmp_path / "storage")
    file_services.storage_manager = manager

    context = CommandExecutionContext(user_id=50001, roles={"user"}, invoker="agent_workflow")

    mkdir_result = await command_executor.execute("mkdir", {"路径": "documents/agent"}, context)
    assert mkdir_result.success
    assert (manager.user_space(50001).home_dir / "documents" / "agent").is_dir()
    report_path = manager.user_space(50001).home_dir / "documents" / "agent" / "report.md"
    report_path.write_text("Agent 文件搜索内容：班会材料已经整理完成。", encoding="utf-8")

    cd_result = await command_executor.execute("cd", {"路径": "documents/agent"}, context)
    assert cd_result.success
    assert cd_result.data["path"] == "~/documents/agent"

    pwd_result = await command_executor.execute("pwd", {}, context)
    assert pwd_result.success
    assert pwd_result.data["path"] == "~/documents/agent"

    find_result = await command_executor.execute("find", {"关键词": "report"}, context)
    assert find_result.success
    assert find_result.data["entries"][0]["path"] == "~/documents/agent/report.md"

    grep_result = await command_executor.execute("grep", {"关键词": "班会"}, context)
    assert grep_result.success
    assert grep_result.data["matches"][0]["path"] == "~/documents/agent/report.md"

    tree_result = await command_executor.execute("tree", {"路径": "~/documents", "深度": 2}, context)
    assert tree_result.success
    assert any("report.md" in line for line in tree_result.data["lines"])


async def test_file_service_group_context_uses_system_group_id(loaded_plugins, tmp_path):
    import src.plugins.application.active.file_manager.services as file_services
    from src.platform.commands import CommandExecutionContext, command_executor
    from src.models import Classes, User
    from src.core.storage import StorageManager

    manager = StorageManager(tmp_path / "storage")
    file_services.storage_manager = manager

    owner = await User.create_user(nickname="群文件创建者", username="file_group_owner_23001")
    classes = await Classes.create_classes(
        name="群文件测试班级",
        platform_name="",
        platform_id="onebot11.qq_client",
        channel_id="23001",
        guild_id=None,
        user=owner,
    )

    context = CommandExecutionContext(
        user_id=owner.id,
        roles={"user"},
        platform="onebot11.qq_client",
        channel_id="23001",
        invoker="agent_workflow",
    )

    mkdir_result = await command_executor.execute(
        "mkdir",
        {"路径": f"群组/{classes.group_id}/documents/group-agent"},
        context,
    )
    assert mkdir_result.success
    assert (manager.group_space(classes.group_id).home_dir / "documents" / "group-agent").is_dir()
    assert not manager.space_root("group", "23001").exists()
