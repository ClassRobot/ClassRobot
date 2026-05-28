from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_message_text_falls_back_when_alconna_cannot_serialize(onebot, monkeypatch, loaded_plugins):
    import src.plugins.library.message_history.collector as collector_module

    def raise_serialize_failed(cls, message, bot=None, adapter=None):
        raise collector_module.SerializeFailed("当前适配器不支持 alconna uniseg")

    monkeypatch.setattr(collector_module.UniMessage, "of", classmethod(raise_serialize_failed))

    event = onebot.private_event("需要兜底的消息", user_id=12001, nickname="兜底用户")
    payload = collector_module.extract_message_text(event)

    assert payload.plain_text == "需要兜底的消息"
    assert payload.raw_text == "需要兜底的消息"
    assert payload.source == collector_module.MessageTextSource.event_fallback
    assert payload.fallback_reason == "SerializeFailed"


async def test_message_text_does_not_fallback_on_unexpected_alconna_error(onebot, monkeypatch, loaded_plugins):
    import src.plugins.library.message_history.collector as collector_module

    def raise_unexpected_error(cls, message, bot=None, adapter=None):
        raise RuntimeError("alconna 内部异常")

    monkeypatch.setattr(collector_module.UniMessage, "of", classmethod(raise_unexpected_error))

    event = onebot.private_event("未知异常不应被吞掉", user_id=12002, nickname="异常用户")
    with pytest.raises(RuntimeError, match="alconna 内部异常"):
        collector_module.extract_message_text(event)


async def test_session_resolver_does_not_fallback_on_unexpected_alconna_error(
    app,
    onebot,
    monkeypatch,
    loaded_plugins,
):
    import src.platform.session.resolvers as resolver_module
    import src.plugins.application.passive.message_history_collector as chat_context_module

    def raise_unexpected_error(event, bot):
        raise RuntimeError("alconna target 内部异常")

    monkeypatch.setattr(resolver_module, "get_target", raise_unexpected_error)

    async with app.test_matcher(chat_context_module.message_history_collector) as ctx:
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("未知 target 异常", user_id=12003, group_id=22003, nickname="异常用户")

        with pytest.raises(RuntimeError, match="alconna target 内部异常"):
            resolver_module.resolve_session_from_event(bot, event)


async def test_group_messages_can_be_collected_and_queried(
    app,
    onebot,
    send_recorder,
    monkeypatch,
    tmp_path,
    loaded_plugins,
):
    from src.models import User, Classes
    import src.plugins.library.message_history.services as services_module
    import src.plugins.library.message_history.collector as collector_module
    import src.plugins.application.passive.message_history_collector as chat_context_module
    from src.plugins.application.active.message_history.commands import query_group_history_cmd
    from src.core.storage import (
        StorageManager,
        ChatHistoryStore,
        MessageActorRole,
        MessageDirection,
        MessageOwnerKind,
        MessageRecordKind,
    )

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    monkeypatch.setattr(collector_module, "chat_history_store", store)
    monkeypatch.setattr(services_module, "chat_history_store", store)

    owner = await User.create_user(nickname="班级创建者", username="chat_context_owner")
    classes = await Classes.create_classes(
        "测试班级",
        platform_name="",
        platform_id="onebot11.qq_client",
        channel_id="23001",
        guild_id=None,
        user=owner,
    )

    async with app.test_matcher(chat_context_module.message_history_collector) as ctx:
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("今天班会要不要调课", user_id=13001, group_id=23001, nickname="张三")
        ctx.receive_event(bot, event)

    async with app.test_matcher(chat_context_module.message_history_collector) as ctx:
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("我不同意临时调课", user_id=13002, group_id=23001, nickname="李四", message_id=2)
        ctx.receive_event(bot, event)

    command_event = onebot.group_event(
        "检索群聊记录 调课", user_id=13003, group_id=23001, nickname="王五", message_id=3
    )

    async with app.test_matcher([chat_context_module.message_history_collector, query_group_history_cmd]) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        ctx.receive_event(bot, command_event)

    records = await store.search_group_messages(classes.group_id, "调课", limit=10, search_window=50)

    assert [record.user_name for record in records] == ["张三", "李四", "王五"]
    assert records[-1].plain_text == "检索群聊记录 调课"
    assert records[-1].direction == MessageDirection.inbound
    assert records[-1].metadata["source"] == "event_collector"
    assert records[-1].metadata["message_source"] == "alconna"
    assert "message_fallback_reason" not in records[-1].metadata
    recorder.assert_any("系统群记录检索", "张三", "调课", "李四", absent=("王五", "检索群聊记录 调课"))

    rows = store._load_recent_rows(MessageOwnerKind.group, classes.group_id, 10, (MessageRecordKind.chat,))
    assert len(rows) == 2
    command_record = store._row_to_record(rows[0])
    reply_record = store._row_to_record(rows[1])
    assert command_record.actor_role == MessageActorRole.user
    assert command_record.direction == MessageDirection.inbound
    assert command_record.plain_text == "检索群聊记录 调课"
    assert command_record.metadata["source"] == "command_input_hook"
    assert command_record.metadata["command_name"] == "检索群聊记录"
    assert reply_record.actor_role == MessageActorRole.assistant
    assert reply_record.direction == MessageDirection.outbound
    assert reply_record.bot_id == "114514"
    assert reply_record.platform_user_id == "114514"
    assert reply_record.metadata["source"] == "bot_send_hook"
    assert "系统群记录检索" in reply_record.plain_text


async def test_group_command_input_and_response_are_recorded_without_message_collector(
    app,
    onebot,
    send_recorder,
    monkeypatch,
    tmp_path,
    loaded_plugins,
):
    from src.models import User, Classes
    import src.plugins.library.message_history.collector as collector_module
    from src.plugins.application.active.file_manager.commands import ls_cmd
    import src.plugins.application.active.file_manager.services as file_services
    from src.core.storage import (
        StorageManager,
        ChatHistoryStore,
        MessageActorRole,
        MessageDirection,
        MessageOwnerKind,
        MessageRecordKind,
    )

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    monkeypatch.setattr(collector_module, "chat_history_store", store)
    monkeypatch.setattr(file_services, "storage_manager", manager)

    owner = await User.create_user(nickname="命令群创建者", username="chat_context_command_only_owner")
    classes = await Classes.create_classes(
        "命令记录测试班级",
        platform_name="",
        platform_id="onebot11.qq_client",
        channel_id="23021",
        guild_id=None,
        user=owner,
    )

    async with app.test_matcher(ls_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("ls", user_id=13021, group_id=23021, nickname="命令用户", message_id=21)
        ctx.receive_event(bot, event)

    rows = store._load_recent_rows(MessageOwnerKind.group, classes.group_id, 10, (MessageRecordKind.chat,))
    records = [store._row_to_record(row) for row in rows]

    assert [record.actor_role for record in records] == [MessageActorRole.user, MessageActorRole.assistant]
    assert records[0].direction == MessageDirection.inbound
    assert records[0].plain_text == "ls"
    assert records[0].metadata["source"] == "command_input_hook"
    assert records[0].metadata["command_name"] == "ls"
    assert records[1].direction == MessageDirection.outbound
    assert records[1].metadata["source"] == "bot_send_hook"
    assert "文件列表" in records[1].plain_text
    recorder.assert_any("文件列表")


async def test_group_history_service_handler_works_in_group_context(monkeypatch, loaded_plugins, tmp_path):
    from src.models import User, Classes
    from src.core.storage import StorageManager, ChatHistoryStore
    import src.plugins.library.message_history.services as services_module
    from src.platform.commands import CommandExecutionContext, command_executor

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    monkeypatch.setattr(services_module, "chat_history_store", store)

    owner = await User.create_user(nickname="系统群创建者", username="chat_context_service_owner")
    classes = await Classes.create_classes(
        "服务测试班级",
        platform_name="",
        platform_id="onebot11.qq_client",
        channel_id="33001",
        guild_id=None,
        user=owner,
    )

    await store.record_group_collect_message(
        group_id=classes.group_id,
        user_id="u1",
        user_name="张三",
        plain_text="关于调课我觉得不合适",
        raw_text="关于调课我觉得不合适",
        message_id="m1",
    )

    result = await command_executor.execute(
        "检索群聊记录",
        {"关键词": ["调课"]},
        CommandExecutionContext(
            platform="onebot11.qq_client",
            channel_id="33001",
            invoker="agent_workflow",
        ),
    )

    assert result.success is True
    assert "系统群记录检索" in result.visible_outputs[0]
    assert "调课" in result.visible_outputs[0]


async def test_chat_statistics_service_counts_current_user_only(monkeypatch, loaded_plugins, tmp_path):
    from src.core.auth import UserRole
    import src.plugins.library.message_history.services as services_module
    from src.platform.commands import CommandExecutionContext, command_executor
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    monkeypatch.setattr(services_module, "chat_history_store", store)

    await store.record_user_chat_message(
        user_id=91001,
        user_name="当前用户",
        plain_text="你好",
        raw_text="你好",
        message_id="u1",
        actor_role=MessageActorRole.user,
    )
    await store.record_user_chat_message(
        user_id=91001,
        user_name="机器人",
        plain_text="你好，我在",
        raw_text="你好，我在",
        message_id="a1",
        actor_role=MessageActorRole.assistant,
    )
    await store.record_user_chat_message(
        user_id=91002,
        user_name="其他用户",
        plain_text="不应该被统计",
        raw_text="不应该被统计",
        message_id="other",
        actor_role=MessageActorRole.user,
    )

    result = await command_executor.execute(
        "统计聊天记录",
        {"范围": "user", "时间范围": "all"},
        CommandExecutionContext(user_id=91001, roles={UserRole.user}, invoker="agent_workflow"),
    )

    assert result.success is True
    assert result.data["scope"] == "user"
    assert result.data["user_id"] == 91001
    assert result.data["total"] == 2
    assert "我们一共聊了 2 条消息" in result.visible_outputs[0]


async def test_chat_statistics_service_counts_bound_system_group_only(monkeypatch, loaded_plugins, tmp_path):
    from datetime import datetime, timedelta

    from src.core.auth import UserRole
    from src.models import User, Classes
    from src.core.storage import StorageManager, ChatHistoryStore
    import src.plugins.library.message_history.services as services_module
    from src.platform.commands import CommandExecutionContext, command_executor

    store = ChatHistoryStore(StorageManager(tmp_path / "storage"))
    monkeypatch.setattr(services_module, "chat_history_store", store)

    owner = await User.create_user(nickname="统计群创建者", username="chat_statistics_group_owner")
    classes = await Classes.create_classes(
        "统计服务测试班级",
        platform_name="",
        platform_id="onebot11.qq_client",
        channel_id="33101",
        guild_id=None,
        user=owner,
    )

    now = datetime.now().replace(microsecond=0)
    store._record_group_message_sync(classes.group_id, "u1", "张三", "第一条", "第一条", "g1", now)
    store._record_group_message_sync(
        classes.group_id, "u2", "李四", "第二条", "第二条", "g2", now + timedelta(seconds=1)
    )
    store._record_group_message_sync("other-group", "u9", "隔壁", "不该统计", "不该统计", "other", now)

    result = await command_executor.execute(
        "统计聊天记录",
        {"范围": "group", "时间范围": "all"},
        CommandExecutionContext(
            platform="onebot11.qq_client",
            channel_id="33101",
            roles={UserRole.user},
            invoker="agent_workflow",
        ),
    )

    assert result.success is True
    assert result.data["scope"] == "group"
    assert result.data["group_id"] == str(classes.group_id)
    assert result.data["total"] == 2
    assert "这个群一共聊了 2 条消息" in result.visible_outputs[0]


async def test_private_messages_are_recorded_under_user_chat_space(app, onebot, monkeypatch, tmp_path, loaded_plugins):
    from src.models import User, UserBind
    from src.core.storage import StorageManager, ChatHistoryStore
    import src.plugins.library.message_history.collector as collector_module
    import src.plugins.application.passive.message_history_collector as chat_context_module

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    monkeypatch.setattr(collector_module, "chat_history_store", store)

    user = await User.create_user(nickname="私聊用户", username="chat_context_private_user")
    await UserBind.bind_user("onebot11.qq_client", "14001", user)

    async with app.test_matcher(chat_context_module.message_history_collector) as ctx:
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("我想问一下奖学金申请", user_id=14001, nickname="私聊用户", message_id=5)
        ctx.receive_event(bot, event)

    records = await store.search_user_chat_messages(user.id, "奖学金", limit=10, search_window=50)

    assert len(records) == 1
    assert records[0].record_kind.value == "chat"
    assert records[0].plain_text == "我想问一下奖学金申请"
    assert records[0].metadata["message_source"] == "alconna"
    assert manager.user_space(user.id).chat_dir.joinpath("messages.db").is_file()


async def test_private_command_input_and_response_are_recorded(
    app,
    onebot,
    send_recorder,
    monkeypatch,
    tmp_path,
    loaded_plugins,
):
    from src.models import User, UserBind
    import src.plugins.library.message_history.collector as collector_module
    from src.plugins.application.active.file_manager.commands import pwd_cmd
    import src.plugins.application.active.file_manager.services as file_services
    import src.plugins.application.passive.message_history_collector as chat_context_module
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole, MessageDirection

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    monkeypatch.setattr(collector_module, "chat_history_store", store)
    monkeypatch.setattr(file_services, "storage_manager", manager)

    user = await User.create_user(nickname="私聊命令用户", username="chat_context_private_command_user")
    await UserBind.bind_user("onebot11.qq_client", "14021", user)
    event = onebot.private_event("pwd", user_id=14021, nickname="私聊命令用户", message_id=21)

    async with app.test_matcher([chat_context_module.message_history_collector, pwd_cmd]) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        ctx.receive_event(bot, event)

    records = await store.search_user_chat_messages(user.id, "", limit=10, search_window=50)
    inbound_record = next(record for record in records if record.actor_role == MessageActorRole.user)
    outbound_record = next(record for record in records if record.actor_role == MessageActorRole.assistant)

    assert inbound_record.direction == MessageDirection.inbound
    assert inbound_record.plain_text == "pwd"
    assert inbound_record.platform_user_id == "14021"
    assert inbound_record.metadata["message_source"] == "alconna"
    assert outbound_record.direction == MessageDirection.outbound
    assert outbound_record.bot_id == "114514"
    assert outbound_record.platform_user_id == "114514"
    assert outbound_record.metadata["source"] == "bot_send_hook"
    recorder.assert_any("~")


async def test_private_assistant_messages_are_recorded_under_user_chat_space(
    monkeypatch, onebot, tmp_path, loaded_plugins
):
    from src.models import User, UserBind
    from src.platform.session import BaseSession
    import src.plugins.library.message_history.collector as collector_module
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    monkeypatch.setattr(collector_module, "chat_history_store", store)

    user = await User.create_user(nickname="私聊用户", username="chat_context_private_reply_user")
    await UserBind.bind_user("onebot11.qq_client", "14011", user)

    platform = BaseSession(
        user_id="14011",
        platform="onebot11.qq_client",
        platform_name="",
        channel_id=None,
        guild_id=None,
    )
    event = onebot.private_event("你好", user_id=14011, nickname="私聊用户", message_id=11)

    await collector_module.record_assistant_message(
        platform,
        event,
        plain_text="这是机器人回复",
        actor_id="114514",
        actor_name="机器人",
        message_id="pm-reply-1",
    )

    records = await store.search_user_chat_messages(user.id, "机器人回复", limit=10, search_window=50)

    assert len(records) == 1
    assert records[0].actor_role == MessageActorRole.assistant
    assert records[0].user_id == "114514"
    assert records[0].user_name == "机器人"


async def test_private_assistant_message_does_not_recreate_deleted_user(monkeypatch, onebot, tmp_path, loaded_plugins):
    from src.models import User, UserBind
    from src.platform.session import BaseSession
    from src.core.storage import StorageManager, ChatHistoryStore
    import src.plugins.library.message_history.collector as collector_module

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    monkeypatch.setattr(collector_module, "chat_history_store", store)

    user = await User.create_user(nickname="待删除用户", username="chat_context_deleted_user")
    await UserBind.bind_user("onebot11.qq_client", "14012", user)
    bind = await UserBind.get_bind("onebot11.qq_client", "14012")
    if bind is not None:
        await bind.delete()
    await user.filter(id=user.id).delete()

    assert await User.filter(id=user.id).first() is None
    assert await UserBind.get_user("onebot11.qq_client", "14012") is None

    platform = BaseSession(
        user_id="14012",
        platform="onebot11.qq_client",
        platform_name="",
        channel_id=None,
        guild_id=None,
    )
    event = onebot.private_event("你好", user_id=14012, nickname="待删除用户", message_id=13)

    await collector_module.record_assistant_message(
        platform,
        event,
        plain_text="这条消息不应该重建用户",
        actor_id="114514",
        actor_name="机器人",
        message_id="pm-reply-deleted",
    )

    assert await UserBind.get_user("onebot11.qq_client", "14012") is None
    assert not manager.root.joinpath("users").exists() or list(manager.root.joinpath("users").iterdir()) == []


async def test_group_assistant_messages_are_recorded_under_group_chat_space(
    monkeypatch, onebot, tmp_path, loaded_plugins
):
    from src.models import User, Classes
    from src.platform.session import BaseSession
    import src.plugins.library.message_history.collector as collector_module
    from src.core.storage import StorageManager, ChatHistoryStore, MessageActorRole, MessageOwnerKind, MessageRecordKind

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    monkeypatch.setattr(collector_module, "chat_history_store", store)

    owner = await User.create_user(nickname="班级创建者", username="chat_context_group_reply_owner")
    classes = await Classes.create_classes(
        "回复测试班级",
        platform_name="",
        platform_id="onebot11.qq_client",
        channel_id="23011",
        guild_id=None,
        user=owner,
    )

    platform = BaseSession(
        user_id="13011",
        platform="onebot11.qq_client",
        platform_name="",
        channel_id="23011",
        guild_id=None,
    )
    event = onebot.group_event("你好", user_id=13011, group_id=23011, nickname="张三", message_id=12)

    await collector_module.record_assistant_message(
        platform,
        event,
        plain_text="群聊里的机器人回复",
        actor_id="114514",
        actor_name="机器人",
        message_id="gm-reply-1",
    )

    rows = store._load_recent_rows(MessageOwnerKind.group, classes.group_id, 10, (MessageRecordKind.chat,))

    assert len(rows) == 1
    record = store._row_to_record(rows[0])
    assert record.actor_role == MessageActorRole.assistant
    assert record.user_name == "机器人"
    assert record.plain_text == "群聊里的机器人回复"


async def test_unbound_platform_group_message_creates_system_group_and_is_persisted(
    app, onebot, monkeypatch, tmp_path, loaded_plugins
):
    from src.models import UserBind, GroupBind
    from src.core.storage import StorageManager, ChatHistoryStore
    import src.plugins.library.message_history.collector as collector_module
    import src.plugins.application.passive.message_history_collector as chat_context_module

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    monkeypatch.setattr(collector_module, "chat_history_store", store)

    async with app.test_matcher(chat_context_module.message_history_collector) as ctx:
        bot = onebot.create_bot(ctx)
        event = onebot.group_event(
            "这是一个未绑定群的消息", user_id=15001, group_id=99999, nickname="路人甲", message_id=7
        )
        ctx.receive_event(bot, event)

    group_bind = await GroupBind.get_bind("onebot11.qq_client", "99999", None)
    assert group_bind is not None
    assert await UserBind.get_user("onebot11.qq_client", "15001") is not None

    records = await store.search_group_messages(group_bind.group_id, "未绑定群", limit=10, search_window=50)
    assert len(records) == 1
    assert records[0].plain_text == "这是一个未绑定群的消息"
    assert manager.group_space(group_bind.group_id).chat_dir.joinpath("messages.db").is_file()
    assert not manager.root.joinpath("groups", "99999").exists()


async def test_create_classes_reuses_auto_created_platform_group(app, onebot, monkeypatch, tmp_path, loaded_plugins):
    from src.models import User, Group, Classes, GroupBind
    from src.core.storage import StorageManager, ChatHistoryStore
    import src.plugins.library.message_history.collector as collector_module
    import src.plugins.application.passive.message_history_collector as chat_context_module

    manager = StorageManager(tmp_path / "storage")
    store = ChatHistoryStore(manager)
    monkeypatch.setattr(collector_module, "chat_history_store", store)

    async with app.test_matcher(chat_context_module.message_history_collector) as ctx:
        bot = onebot.create_bot(ctx)
        event = onebot.group_event("先创建一个系统群", user_id=15011, group_id=99111, nickname="张三", message_id=11)
        ctx.receive_event(bot, event)

    original_bind = await GroupBind.get_bind("onebot11.qq_client", "99111", None)
    assert original_bind is not None
    original_group_id = original_bind.group_id

    owner = await User.create_user(nickname="建班教师", username="chat_context_group_owner")
    classes = await Classes.create_classes(
        "复用系统群班级",
        platform_name="QQ",
        platform_id="onebot11.qq_client",
        channel_id="99111",
        guild_id=None,
        user=owner,
    )

    binds = await GroupBind.filter(platform_id="onebot11.qq_client", channel_id="99111").all()
    assert len(binds) == 1
    assert binds[0].group_id == classes.group_id == original_group_id

    group = await Group.filter(id=original_group_id).first()
    assert group is not None
    assert group.name == "复用系统群班级"
    assert group.creator_id == owner.id
