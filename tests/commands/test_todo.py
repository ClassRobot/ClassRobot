from __future__ import annotations

import pytest
from src.platform.commands.context import CommandInvoker

pytestmark = pytest.mark.asyncio


def _user_context(user, *, invoker: "CommandInvoker" = "user_command"):
    """构建当前用户的命令执行上下文。"""

    from src.core.auth import UserRole
    from src.platform.commands import CommandExecutionContext

    return CommandExecutionContext(
        user_id=user.id,
        roles=set(user.roles) or {UserRole.user},
        invoker=invoker,
    )


async def test_create_todo_persists_and_returns_detail(loaded_plugins, models):
    from src.models import Todo
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31001, nickname="待办用户")

    result = await command_executor.execute(
        "创建待办",
        {"标题": "提交实验报告", "截止时间": "2026-05-30 14:00", "备注": "附数据图"},
        _user_context(user),
    )

    assert result.success is True
    todo_id = result.data["todo_id"]
    stored = await Todo.get_owned(user.id, todo_id)
    assert stored is not None
    assert stored.title == "提交实验报告"
    assert stored.content == "附数据图"
    assert stored.due_at is not None
    assert "提交实验报告" in result.visible_outputs[0]


async def test_create_todo_rejects_empty_title(loaded_plugins, models):
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31002, nickname="空标题用户")

    result = await command_executor.execute("创建待办", {"标题": "   "}, _user_context(user))

    assert result.success is False
    assert "标题不能为空" in result.summary


async def test_create_todo_rejects_invalid_due(loaded_plugins, models):
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31003, nickname="非法时间用户")

    result = await command_executor.execute(
        "创建待办",
        {"标题": "无效时间待办", "截止时间": "明天"},
        _user_context(user),
    )

    assert result.success is False
    assert "无法识别的时间格式" in result.summary


async def test_query_todo_defaults_to_pending(loaded_plugins, models):
    from src.models import Todo
    from src.models.models import TodoStatus
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31004, nickname="查询用户")
    await Todo.create_todo(user.id, "待处理项")
    done = await Todo.create_todo(user.id, "已完成项")
    await done.update(status=TodoStatus.done)

    result = await command_executor.execute("查询待办", {}, _user_context(user))

    assert result.success is True
    titles = [item["title"] for item in result.data["todos"]]
    assert "待处理项" in titles
    assert "已完成项" not in titles
    assert result.data["status"] == TodoStatus.pending.value


async def test_query_todo_can_filter_all_status(loaded_plugins, models):
    from src.models import Todo
    from src.models.models import TodoStatus
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31005, nickname="全部查询用户")
    await Todo.create_todo(user.id, "待处理项")
    done = await Todo.create_todo(user.id, "已完成项")
    await done.update(status=TodoStatus.done)

    result = await command_executor.execute("查询待办", {"状态": "全部"}, _user_context(user))

    assert result.success is True
    titles = {item["title"] for item in result.data["todos"]}
    assert {"待处理项", "已完成项"} <= titles


async def test_query_todo_rejects_unknown_status(loaded_plugins, models):
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31006, nickname="非法状态用户")

    result = await command_executor.execute("查询待办", {"状态": "随便"}, _user_context(user))

    assert result.success is False
    assert "无法识别的待办状态" in result.summary


async def test_complete_todo_transitions_status(loaded_plugins, models):
    from src.models import Todo
    from src.models.models import TodoStatus
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31007, nickname="完成用户")
    todo = await Todo.create_todo(user.id, "待完成项")

    result = await command_executor.execute("完成待办", {"待办ID": todo.id}, _user_context(user))

    assert result.success is True
    refreshed = await Todo.get_owned(user.id, todo.id)
    assert refreshed is not None
    assert refreshed.status == TodoStatus.done
    assert refreshed.completed_at is not None


async def test_complete_todo_rejects_other_users_todo(loaded_plugins, models):
    from src.models import Todo
    from src.models.models import TodoStatus
    from src.platform.commands import command_executor

    owner = await models.create_user(account_id=31008, nickname="归属用户")
    other = await models.create_user(account_id=31009, nickname="越权用户")
    todo = await Todo.create_todo(owner.id, "他人待办")

    result = await command_executor.execute("完成待办", {"待办ID": todo.id}, _user_context(other))

    assert result.success is False
    assert "不属于您" in result.summary
    untouched = await Todo.get_owned(owner.id, todo.id)
    assert untouched is not None
    assert untouched.status == TodoStatus.pending


async def test_delete_todo_removes_only_owned_record(loaded_plugins, models):
    from src.models import Todo
    from src.platform.commands import command_executor

    owner = await models.create_user(account_id=31010, nickname="删除归属用户")
    other = await models.create_user(account_id=31011, nickname="删除越权用户")
    todo = await Todo.create_todo(owner.id, "待删除项")

    denied = await command_executor.execute("删除待办", {"待办ID": todo.id}, _user_context(other))
    assert denied.success is False
    assert await Todo.get_owned(owner.id, todo.id) is not None

    allowed = await command_executor.execute("删除待办", {"待办ID": todo.id}, _user_context(owner))
    assert allowed.success is True
    assert await Todo.get_owned(owner.id, todo.id) is None


async def test_delete_todo_is_not_agent_callable(loaded_plugins, models):
    from src.models import Todo
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31012, nickname="Agent删除用户")
    todo = await Todo.create_todo(user.id, "Agent不可删项")

    result = await command_executor.execute(
        "删除待办", {"待办ID": todo.id}, _user_context(user, invoker="agent_workflow")
    )

    assert result.success is False
    assert await Todo.get_owned(user.id, todo.id) is not None


async def test_query_and_create_todo_are_agent_callable(loaded_plugins, models):
    from src.platform.commands import command_executor

    user = await models.create_user(account_id=31013, nickname="Agent待办用户")

    created = await command_executor.execute(
        "创建待办",
        {"标题": "Agent创建项"},
        _user_context(user, invoker="agent_workflow"),
    )
    queried = await command_executor.execute("查询待办", {}, _user_context(user, invoker="agent_workflow"))

    assert created.success is True
    assert queried.success is True
    assert any(item["title"] == "Agent创建项" for item in queried.data["todos"])


async def test_todo_commands_exposed_in_agent_tool_catalog(loaded_plugins):
    from src.platform.helper import Helpers
    from src.platform.commands import command_registry
    from src.core.agent.runtime.command_tools import CommandToolCatalog
    from src.platform.commands.renderers.helper import command_spec_to_helper

    helpers = Helpers()
    for name in ("创建待办", "查询待办", "完成待办", "删除待办"):
        spec = command_registry.get(name)
        assert spec is not None, f"命令 {name} 未注册到命令注册表"
        helpers.append(command_spec_to_helper(spec))

    catalog = CommandToolCatalog.from_helpers(helpers)

    # agent_callable=True 且 service 化的待办命令应进入 Agent 工具目录。
    assert catalog.get("创建待办") is not None
    assert catalog.get("查询待办") is not None
    assert catalog.get("完成待办") is not None
    # 删除待办 agent_callable=False，不应暴露给 Agent。
    assert catalog.get("删除待办") is None


async def test_user_command_can_create_query_complete_and_delete_todo(app, onebot, send_recorder, models):
    from src.models import Todo
    from src.models.models import TodoStatus
    from src.plugins.application.active.todo.commands import (
        query_todo_cmd,
        create_todo_cmd,
        delete_todo_cmd,
        complete_todo_cmd,
    )

    user = await models.create_user(account_id=31014, nickname="黑盒待办用户")

    async with app.test_matcher(create_todo_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(
            "创建待办 黑盒待办 2026-05-30 14:00 黑盒备注", user_id=31014, nickname="黑盒待办用户"
        )
        ctx.receive_event(bot, event)

    recorder.assert_any("已创建待办", "黑盒待办", "黑盒备注")
    todo = await Todo.filter(owner_user_id=user.id, title="黑盒待办").first()
    assert todo is not None
    assert todo.content == "黑盒备注"
    assert todo.due_at is not None
    assert todo.due_at.hour == 14
    assert todo.due_at.minute == 0

    async with app.test_matcher(query_todo_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("查询待办", user_id=31014, nickname="黑盒待办用户", message_id=2)
        ctx.receive_event(bot, event)

    recorder.assert_any("您的待办", "黑盒待办")

    async with app.test_matcher(complete_todo_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(f"完成待办 {todo.id}", user_id=31014, nickname="黑盒待办用户", message_id=3)
        ctx.receive_event(bot, event)

    recorder.assert_any("已完成待办", "黑盒待办")
    completed = await Todo.get_owned(user.id, todo.id)
    assert completed is not None
    assert completed.status == TodoStatus.done

    async with app.test_matcher(delete_todo_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(f"删除待办 {todo.id}", user_id=31014, nickname="黑盒待办用户", message_id=4)
        ctx.receive_event(bot, event)

    recorder.assert_any("已删除待办", "黑盒待办")
    assert await Todo.get_owned(user.id, todo.id) is None


async def test_user_command_create_todo_can_prompt_then_accept_completed_command(app, onebot, send_recorder, models):
    from src.models import Todo
    from src.plugins.application.active.todo.commands import create_todo_cmd

    user = await models.create_user(account_id=31015, nickname="补参待办用户")

    async with app.test_matcher(create_todo_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        prompt = onebot.private_event("创建待办", user_id=31015, nickname="补参待办用户")
        ctx.receive_event(bot, prompt)

    recorder.assert_any("请输入待办标题")
    assert await Todo.filter(owner_user_id=user.id, title="补参待办").first() is None

    async with app.test_matcher(create_todo_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event("创建待办 补参待办", user_id=31015, nickname="补参待办用户")
        ctx.receive_event(bot, event)

    recorder.assert_any("已创建待办", "补参待办")
    todo = await Todo.filter(owner_user_id=user.id, title="补参待办").first()
    assert todo is not None


async def test_user_command_rejects_cross_user_complete_and_delete(app, onebot, send_recorder, models):
    from src.models import Todo
    from src.models.models import TodoStatus
    from src.plugins.application.active.todo.commands import delete_todo_cmd, complete_todo_cmd

    owner = await models.create_user(account_id=31016, nickname="待办归属用户")
    await models.create_user(account_id=31017, nickname="待办越权用户")
    todo = await Todo.create_todo(owner.id, "边界待办")

    async with app.test_matcher(complete_todo_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(f"完成待办 {todo.id}", user_id=31017, nickname="待办越权用户")
        ctx.receive_event(bot, event)

    recorder.assert_any("不属于您")
    unchanged = await Todo.get_owned(owner.id, todo.id)
    assert unchanged is not None
    assert unchanged.status == TodoStatus.pending

    async with app.test_matcher(delete_todo_cmd) as ctx:
        recorder = send_recorder(ctx)
        bot = onebot.create_bot(ctx)
        event = onebot.private_event(f"删除待办 {todo.id}", user_id=31017, nickname="待办越权用户", message_id=2)
        ctx.receive_event(bot, event)

    recorder.assert_any("不属于您")
    assert await Todo.get_owned(owner.id, todo.id) is not None
