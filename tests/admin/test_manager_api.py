import os
import sys
from pathlib import Path
from uuid import uuid4

import nonebot
import httpx
import pytest
import pytest_asyncio
from dotenv import dotenv_values
from sqlalchemy import Boolean, Column, ForeignKey, Integer, MetaData, String, Table, delete

pytestmark = pytest.mark.asyncio


async def _recreate_admin_orm_schema() -> None:
    import nonebot_plugin_orm as orm

    if not hasattr(orm, "_metadatas") or not getattr(orm, "_metadatas", None):
        orm._init_orm()
    if hasattr(orm, "_scoped_sessions"):
        await orm._scoped_sessions.remove()
    for bind_name, metadata in orm._metadatas.items():
        engine = orm._engines[bind_name]
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
            await connection.run_sync(metadata.create_all)


@pytest.fixture(scope="session")
def manager_app(loaded_plugins):
    import src.routers.path  # noqa: F401

    return nonebot.get_app()


@pytest_asyncio.fixture
async def manager_client(manager_app):
    transport = httpx.ASGITransport(app=manager_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(autouse=True)
def reset_manager_tokens():
    from src.routers.managers.security import token_store

    token_store.rotate_startup_token(log_token=False)
    yield
    token_store._sessions.clear()  # noqa: SLF001


@pytest.fixture(autouse=True)
def isolate_manager_audit_log(monkeypatch, tmp_path):
    from src.routers.managers import audit
    from src.routers.managers import operations

    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", tmp_path / "manager_audit.jsonl")
    monkeypatch.setattr(operations, "AUTOMATION_SCRIPT_PATH", tmp_path / "manager_automation_scripts.json")


@pytest_asyncio.fixture
async def manager_auth_headers(manager_client):
    from src.routers.managers.security import token_store

    response = await manager_client.post(
        "/api/v1/manager/auth/login",
        json={"token": token_store._startup_token},  # noqa: SLF001
    )
    assert response.status_code == 200, response.text
    access_token = response.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def manager_workflow_tables(loaded_plugins):
    from nonebot_plugin_orm import get_session
    from utils.models import AgentWorkflowCheckpoint, AgentWorkflowRun

    async with get_session() as session:
        bind = session.bind
        assert bind is not None

    async with bind.begin() as connection:
        await connection.run_sync(AgentWorkflowCheckpoint.__table__.create, checkfirst=True)
        await connection.run_sync(AgentWorkflowRun.__table__.create, checkfirst=True)

    async with get_session() as session:
        await session.execute(delete(AgentWorkflowCheckpoint))
        await session.execute(delete(AgentWorkflowRun))
        await session.commit()

    yield

    async with get_session() as session:
        await session.execute(delete(AgentWorkflowCheckpoint))
        await session.execute(delete(AgentWorkflowRun))
        await session.commit()


@pytest_asyncio.fixture
async def manager_database_tables(loaded_plugins):
    from nonebot_plugin_orm import get_session

    metadata = MetaData()
    parent = Table(
        "manager_db_parent",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(64), nullable=False),
    )
    child = Table(
        "manager_db_child",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", Integer, ForeignKey("manager_db_parent.id"), nullable=False),
        Column("label", String(64), nullable=False),
        Column("active", Boolean, nullable=False),
    )

    async with get_session() as session:
        bind = session.bind
        assert bind is not None

    async with bind.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(parent.insert(), {"id": 1, "name": "parent"})
        await connection.execute(
            child.insert(),
            {"id": 10, "parent_id": 1, "label": "child-before", "active": True},
        )

    yield {"parent": parent, "child": child}

    async with bind.begin() as connection:
        await connection.run_sync(metadata.drop_all)


@pytest_asyncio.fixture
async def manager_user_orm(loaded_plugins):
    await _recreate_admin_orm_schema()
    yield


@pytest_asyncio.fixture
async def seeded_manager_checkpoint(manager_workflow_tables):
    from utils.models import AgentWorkflowCheckpoint

    return await AgentWorkflowCheckpoint(
        user_id=88,
        trace_id="trace-manager-88",
        kind="chat",
        status="needs_confirm",
        goal="测试检查点",
        summary="等待确认",
        workflow_data={"step": 1},
    ).create()


async def test_manager_auth_flow(manager_client):
    from src.routers.managers.security import token_store

    unauthorized = await manager_client.get("/api/v1/manager/auth/me")
    assert unauthorized.status_code == 401

    login = await manager_client.post(
        "/api/v1/manager/auth/login",
        json={"token": token_store._startup_token},  # noqa: SLF001
    )
    assert login.status_code == 200, login.text
    payload = login.json()
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] > 0

    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    me = await manager_client.get("/api/v1/manager/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["authenticated"] is True

    logout = await manager_client.post("/api/v1/manager/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert logout.json() == {"logged_out": True}

    expired = await manager_client.get("/api/v1/manager/auth/me", headers=headers)
    assert expired.status_code == 401


async def test_manager_settings_masks_secrets_and_rejects_invalid_keys(manager_client, manager_auth_headers):
    response = await manager_client.get("/api/v1/manager/settings", headers=manager_auth_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["cos"]["cos_secret_id"] != os.environ["COS_SECRET_ID"]
    assert payload["cos"]["cos_secret_key"] != os.environ["COS_SECRET_KEY"]
    assert payload["cos"]["cos_secret_id"].startswith("test")
    assert payload["cos"]["cos_secret_key"].endswith("-key")

    invalid = await manager_client.patch(
        "/api/v1/manager/settings",
        headers=manager_auth_headers,
        json={"base": {"unsupported": True}},
    )
    assert invalid.status_code == 400
    assert "Unsupported setting keys" in invalid.json()["detail"]


async def test_manager_settings_update_writes_temp_env(manager_client, manager_auth_headers, monkeypatch, tmp_path):
    from src.routers.managers import settings_store

    env_path = tmp_path / ".env"
    env_path.write_text("GLOBAL_PROXY=http://old.example\n", "utf-8")
    monkeypatch.setattr(settings_store, "ENV_PATH", env_path)

    response = await manager_client.patch(
        "/api/v1/manager/settings",
        headers=manager_auth_headers,
        json={
            "base": {
                "global_proxy": "http://127.0.0.1:7890",
                "teacher_max_classes": 8,
            },
            "cache": {
                "cache_host": "127.0.0.1",
                "cache_port": 6380,
            },
        },
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["saved"] is True
    assert payload["restart_required"] is True
    assert payload["changed_keys"] == [
        "GLOBAL_PROXY",
        "TEACHER_MAX_CLASSES",
        "CACHE_HOST",
        "CACHE_PORT",
    ]

    saved_env = dotenv_values(env_path)
    assert saved_env["GLOBAL_PROXY"] == "http://127.0.0.1:7890"
    assert saved_env["TEACHER_MAX_CLASSES"] == "8"
    assert saved_env["CACHE_HOST"] == "127.0.0.1"
    assert saved_env["CACHE_PORT"] == "6380"
    assert env_path.with_suffix(".env.manager-backup").exists()


async def test_manager_models_validate_payload(manager_client, manager_auth_headers, monkeypatch, tmp_path):
    from src.routers.managers import settings_store

    env_path = tmp_path / ".env"
    monkeypatch.setattr(settings_store, "ENV_PATH", env_path)

    invalid_timeout = await manager_client.put(
        "/api/v1/manager/models",
        headers=manager_auth_headers,
        json={"llm_timeout": 0},
    )
    assert invalid_timeout.status_code == 400
    assert "models.llm_timeout" in invalid_timeout.json()["detail"]

    duplicate_names = await manager_client.put(
        "/api/v1/manager/models",
        headers=manager_auth_headers,
        json={
            "llm_configs": [
                {
                    "name": "primary",
                    "key": "sk-1",
                    "url": "https://api.example.com/v1",
                    "model": "gpt-test",
                },
                {
                    "name": "primary",
                    "key": "sk-2",
                    "url": "https://api.example.com/v1",
                    "model": "gpt-test-2",
                },
            ]
        },
    )
    assert duplicate_names.status_code == 400
    assert "duplicate model name" in duplicate_names.json()["detail"]

    missing = await manager_client.post(
        "/api/v1/manager/models/not-found/test",
        headers=manager_auth_headers,
    )
    assert missing.status_code == 404


async def test_manager_prompts_validate_update_and_reject_invalid_name(
    manager_client,
    manager_auth_headers,
    monkeypatch,
    tmp_path,
):
    from src.routers.managers import prompts

    prompts_root = tmp_path / "prompts"
    prompts_root.mkdir()
    prompt_path = prompts_root / "sample.jinja"
    prompt_path.write_text("Hello {{ name }}!\n", "utf-8")

    backup_root = tmp_path / "config"
    monkeypatch.setattr(prompts, "prompts_dir", prompts_root)
    monkeypatch.setattr(prompts, "config_dir", backup_root)

    invalid_name = await manager_client.get(
        "/api/v1/manager/prompts/..%5Csecret",
        headers=manager_auth_headers,
    )
    assert invalid_name.status_code == 400

    detail = await manager_client.get("/api/v1/manager/prompts/sample", headers=manager_auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["content"] == "Hello {{ name }}!\n"

    updated = await manager_client.put(
        "/api/v1/manager/prompts/sample",
        headers=manager_auth_headers,
        json={"content": "Hi {{ user }}!\n"},
    )
    assert updated.status_code == 200, updated.text
    updated_payload = updated.json()
    assert updated_payload["saved"] is True
    assert Path(updated_payload["backup_path"]).exists()
    assert prompt_path.read_text("utf-8") == "Hi {{ user }}!\n"

    validated = await manager_client.post("/api/v1/manager/prompts/sample/validate", headers=manager_auth_headers)
    assert validated.status_code == 200
    assert validated.json()["valid"] is True

    invalid_template = await manager_client.put(
        "/api/v1/manager/prompts/sample",
        headers=manager_auth_headers,
        json={"content": "{% if user %}\n"},
    )
    assert invalid_template.status_code == 200
    assert invalid_template.json()["saved"] is False
    assert invalid_template.json()["valid"] is False
    assert prompt_path.read_text("utf-8") == "Hi {{ user }}!\n"


async def test_safe_prompt_path_rejects_cross_platform_traversal():
    from src.routers.managers.prompts import _safe_prompt_path

    with pytest.raises(ValueError):
        _safe_prompt_path("..\\secret")


async def test_manager_logs_limit_access_to_allowed_roots(manager_client, manager_auth_headers, monkeypatch, tmp_path):
    from src.routers.managers import logs

    allowed_root = tmp_path / "logs"
    allowed_root.mkdir()
    allowed_path = allowed_root / "app.log"
    allowed_path.write_text("first\nsecond\nthird\n", "utf-8")

    forbidden_path = tmp_path / "secret.log"
    forbidden_path.write_text("nope\n", "utf-8")
    monkeypatch.setattr(logs, "LOG_ROOTS", (allowed_root,))

    listing = await manager_client.get("/api/v1/manager/logs", headers=manager_auth_headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0]["path"] == str(allowed_path.resolve())

    read_ok = await manager_client.get(
        "/api/v1/manager/logs/read",
        headers=manager_auth_headers,
        params={"path": str(allowed_path.resolve()), "offset": 1, "limit": 1},
    )
    assert read_ok.status_code == 200, read_ok.text
    assert read_ok.json()["lines"] == ["second"]

    forbidden = await manager_client.get(
        "/api/v1/manager/logs/read",
        headers=manager_auth_headers,
        params={"path": str(forbidden_path.resolve())},
    )
    assert forbidden.status_code == 403

    tail_ok = await manager_client.get(
        "/api/v1/manager/logs/tail",
        headers=manager_auth_headers,
        params={"path": str(allowed_path.resolve()), "lines": 2},
    )
    assert tail_ok.status_code == 200, tail_ok.text
    assert tail_ok.json()["lines"] == ["second", "third"]


async def test_manager_system_metrics_include_resource_usage(manager_client, manager_auth_headers):
    response = await manager_client.get("/api/v1/manager/system/metrics", headers=manager_auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] in {"ok", "warning", "error"}
    assert payload["cpu"]["count"] >= 1
    assert isinstance(payload["disks"], list)


async def test_manager_operations_list_run_and_404_missing_action(manager_client, manager_auth_headers, monkeypatch):
    from src.routers.managers import operations

    async def sample_action():
        return {"ok": True, "message": "sample"}

    monkeypatch.setitem(
        operations.ACTION_REGISTRY,
        "sample_action",
        {"title": "示例动作", "risk": "low", "handler": sample_action},
    )

    listing = await manager_client.get("/api/v1/manager/operations/actions", headers=manager_auth_headers)
    assert listing.status_code == 200, listing.text
    action_ids = {item["action_id"] for item in listing.json()["items"]}
    assert "sample_action" in action_ids

    run = await manager_client.post(
        "/api/v1/manager/operations/actions/sample_action/run", headers=manager_auth_headers
    )
    assert run.status_code == 200, run.text
    run_payload = run.json()
    assert run_payload["status"] == "completed"
    assert run_payload["result"]["message"] == "sample"

    missing = await manager_client.post(
        "/api/v1/manager/operations/actions/missing/run",
        headers=manager_auth_headers,
    )
    assert missing.status_code == 404

    audit_log = await manager_client.get("/api/v1/manager/operations/audit-log", headers=manager_auth_headers)
    assert audit_log.status_code == 200, audit_log.text
    assert any(item["action"] == "sample_action" for item in audit_log.json()["items"])


async def test_manager_terminal_commands_are_allowlisted_and_audited(manager_client, manager_auth_headers):
    listing = await manager_client.get("/api/v1/manager/operations/terminal/commands", headers=manager_auth_headers)
    assert listing.status_code == 200, listing.text
    command_ids = {item["command_id"] for item in listing.json()["items"]}
    assert "list_project_root" in command_ids

    run = await manager_client.post(
        "/api/v1/manager/operations/terminal/commands/list_project_root/run",
        headers=manager_auth_headers,
    )
    assert run.status_code == 200, run.text
    run_payload = run.json()
    assert run_payload["command_id"] == "list_project_root"
    assert run_payload["status"] == "completed"
    assert "pyproject.toml" in run_payload["stdout"]

    missing = await manager_client.post(
        "/api/v1/manager/operations/terminal/commands/not_allowed/run",
        headers=manager_auth_headers,
    )
    assert missing.status_code == 404

    audit_log = await manager_client.get(
        "/api/v1/manager/operations/audit-log",
        headers=manager_auth_headers,
        params={"event_type": "terminal"},
    )
    assert audit_log.status_code == 200, audit_log.text
    assert audit_log.json()["items"][0]["action"] == "list_project_root"


async def test_manager_direct_terminal_and_custom_scripts(manager_client, manager_auth_headers, tmp_path):
    direct = await manager_client.post(
        "/api/v1/manager/operations/terminal/run",
        headers=manager_auth_headers,
        json={
            "command": f'"{sys.executable}" -c "print(\'direct-ok\')"',
            "cwd": str(tmp_path),
            "timeout": 10,
        },
    )
    assert direct.status_code == 200, direct.text
    direct_payload = direct.json()
    assert direct_payload["status"] == "completed"
    assert "direct-ok" in direct_payload["stdout"]
    assert direct_payload["cwd"] == str(tmp_path.resolve())

    changed_dir = await manager_client.post(
        "/api/v1/manager/operations/terminal/run",
        headers=manager_auth_headers,
        json={"command": "cd ..", "cwd": str(tmp_path), "timeout": 10},
    )
    assert changed_dir.status_code == 200, changed_dir.text
    assert changed_dir.json()["status"] == "completed"
    assert changed_dir.json()["cwd"] == str(tmp_path.parent.resolve())

    created = await manager_client.post(
        "/api/v1/manager/operations/scripts",
        headers=manager_auth_headers,
        json={
            "id": "test_script",
            "title": "测试脚本",
            "description": "script smoke test",
            "command": f'"{sys.executable}" -c "print(\'script-ok\')"',
            "cwd": str(tmp_path),
            "risk": "low",
            "timeout": 10,
            "enabled": True,
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["id"] == "test_script"

    listing = await manager_client.get("/api/v1/manager/operations/scripts", headers=manager_auth_headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0]["id"] == "test_script"

    updated = await manager_client.patch(
        "/api/v1/manager/operations/scripts/test_script",
        headers=manager_auth_headers,
        json={"title": "更新后的脚本", "risk": "medium"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "更新后的脚本"
    assert updated.json()["risk"] == "medium"

    run = await manager_client.post(
        "/api/v1/manager/operations/scripts/test_script/run",
        headers=manager_auth_headers,
    )
    assert run.status_code == 200, run.text
    assert run.json()["status"] == "completed"
    assert "script-ok" in run.json()["stdout"]

    audit_log = await manager_client.get(
        "/api/v1/manager/operations/audit-log",
        headers=manager_auth_headers,
        params={"event_type": "script"},
    )
    assert audit_log.status_code == 200, audit_log.text
    actions = [item["action"] for item in audit_log.json()["items"]]
    assert "test_script" in actions
    assert "create_script" in actions

    deleted = await manager_client.delete(
        "/api/v1/manager/operations/scripts/test_script",
        headers=manager_auth_headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True, "id": "test_script"}


async def test_manager_database_catalog_rows_and_update(
    manager_client,
    manager_auth_headers,
    manager_database_tables,
):
    connections = await manager_client.get("/api/v1/manager/databases", headers=manager_auth_headers)
    assert connections.status_code == 200, connections.text
    connection_payload = connections.json()
    assert connection_payload["items"][0]["id"] == "primary"
    assert connection_payload["items"][0]["editable"] is True

    schema = await manager_client.get("/api/v1/manager/databases/primary/schema", headers=manager_auth_headers)
    assert schema.status_code == 200, schema.text
    schema_payload = schema.json()
    table_names = {item["name"] for item in schema_payload["tables"]}
    assert {"manager_db_parent", "manager_db_child"}.issubset(table_names)
    relationships = {(item["source_table"], item["target_table"]) for item in schema_payload["relationships"]}
    assert ("manager_db_child", "manager_db_parent") in relationships

    tables = await manager_client.get("/api/v1/manager/databases/primary/tables", headers=manager_auth_headers)
    assert tables.status_code == 200, tables.text
    child_table = next(item for item in tables.json()["items"] if item["name"] == "manager_db_child")
    assert child_table["row_count"] == 1
    assert child_table["primary_key"] == ["id"]
    assert child_table["foreign_key_count"] == 1

    rows = await manager_client.get(
        "/api/v1/manager/databases/primary/tables/manager_db_child/rows",
        headers=manager_auth_headers,
        params={"page_size": 5},
    )
    assert rows.status_code == 200, rows.text
    rows_payload = rows.json()
    assert rows_payload["total"] == 1
    assert rows_payload["items"][0]["label"] == "child-before"

    updated = await manager_client.patch(
        "/api/v1/manager/databases/primary/tables/manager_db_child/rows",
        headers=manager_auth_headers,
        json={"pk": {"id": 10}, "values": {"label": "child-after"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["row"]["label"] == "child-after"

    invalid = await manager_client.patch(
        "/api/v1/manager/databases/primary/tables/manager_db_child/rows",
        headers=manager_auth_headers,
        json={"pk": {"id": 10}, "values": {"missing": "nope"}},
    )
    assert invalid.status_code == 400
    invalid_detail = invalid.json()["detail"]
    assert invalid_detail["code"] == "unknown_update_column"
    assert invalid_detail["columns"] == ["missing"]


async def test_manager_database_update_errors_are_structured(
    manager_client,
    manager_auth_headers,
    manager_database_tables,
):
    endpoint = "/api/v1/manager/databases/primary/tables/manager_db_child/rows"

    missing_pk = await manager_client.patch(
        endpoint,
        headers=manager_auth_headers,
        json={"pk": {}, "values": {"label": "next"}},
    )
    assert missing_pk.status_code == 400
    assert missing_pk.json()["detail"]["code"] == "primary_key_required"

    primary_key_update = await manager_client.patch(
        endpoint,
        headers=manager_auth_headers,
        json={"pk": {"id": 10}, "values": {"id": 11}},
    )
    assert primary_key_update.status_code == 400
    primary_key_detail = primary_key_update.json()["detail"]
    assert primary_key_detail["code"] == "primary_key_update_forbidden"
    assert primary_key_detail["columns"] == ["id"]

    invalid_integer = await manager_client.patch(
        endpoint,
        headers=manager_auth_headers,
        json={"pk": {"id": 10}, "values": {"parent_id": "not-a-number"}},
    )
    assert invalid_integer.status_code == 400
    integer_detail = invalid_integer.json()["detail"]
    assert integer_detail["code"] == "invalid_integer"
    assert integer_detail["column"] == "parent_id"
    assert integer_detail["expected"] == "整数"

    invalid_boolean = await manager_client.patch(
        endpoint,
        headers=manager_auth_headers,
        json={"pk": {"id": 10}, "values": {"active": "maybe"}},
    )
    assert invalid_boolean.status_code == 400
    boolean_detail = invalid_boolean.json()["detail"]
    assert boolean_detail["code"] == "invalid_boolean"
    assert boolean_detail["column"] == "active"

    null_label = await manager_client.patch(
        endpoint,
        headers=manager_auth_headers,
        json={"pk": {"id": 10}, "values": {"label": None}},
    )
    assert null_label.status_code == 400
    null_detail = null_label.json()["detail"]
    assert null_detail["code"] == "null_not_allowed"
    assert null_detail["column"] == "label"

    missing_row = await manager_client.patch(
        endpoint,
        headers=manager_auth_headers,
        json={"pk": {"id": 999}, "values": {"label": "next"}},
    )
    assert missing_row.status_code == 400
    assert missing_row.json()["detail"]["code"] == "row_not_found"


async def test_manager_user_delete_removes_user_and_binds(manager_client, manager_auth_headers, manager_user_orm):
    from utils.models import User, UserBind

    suffix = uuid4().hex[:8]
    user = await User.create_user(nickname="待删用户", username=f"manager_delete_user_{suffix}")
    await UserBind.bind_user("qq.qq_api", f"manager-delete-{suffix}", user)

    response = await manager_client.delete(f"/api/v1/manager/users/{user.id}", headers=manager_auth_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": True, "user_id": user.id}
    assert await User.filter(id=user.id).first() is None
    assert await UserBind.filter(user_id=user.id).count() == 0


async def test_manager_users_include_avatar_in_summary_and_detail(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
):
    from utils.models import User

    suffix = uuid4().hex[:8]
    avatar_url = f"https://example.com/avatar-{suffix}.png"
    user = await User.create_user(
        nickname="头像用户",
        username=f"manager_avatar_user_{suffix}",
        avatar=avatar_url,
    )

    summary_response = await manager_client.get("/api/v1/manager/users", headers=manager_auth_headers)
    assert summary_response.status_code == 200, summary_response.text
    summary_items = summary_response.json()["items"]
    summary_item = next(item for item in summary_items if item["id"] == user.id)
    assert summary_item["avatar"] == avatar_url

    detail_response = await manager_client.get(
        f"/api/v1/manager/users/{user.id}",
        headers=manager_auth_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["avatar"] == avatar_url


async def test_manager_groups_list_and_detail(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
):
    from utils.models import Classes, Teacher, User

    suffix = uuid4().hex[:8]
    creator = await User.create_user(nickname="群组创建者", username=f"manager_group_creator_{suffix}")
    teacher_user = await User.create_user(nickname="群组教师", username=f"manager_group_teacher_{suffix}")
    teacher = await Teacher.create_teacher("群组教师", teacher_user)
    classes = await Classes.create_classes(
        name=f"管理测试班级_{suffix}",
        platform_name="QQ",
        platform_id="qq.qq_api",
        channel_id=f"manager-group-{suffix}",
        guild_id=None,
        user=creator,
    )
    await classes.bind_teacher(teacher)

    response = await manager_client.get(
        "/api/v1/manager/groups",
        headers=manager_auth_headers,
        params={"q": suffix},
    )
    assert response.status_code == 200, response.text
    item = next(group for group in response.json()["items"] if group["id"] == classes.group_id)
    assert item["class_info"]["name"] == classes.name
    assert item["creator"]["id"] == creator.id
    assert item["platforms"] == ["qq.qq_api"]
    assert item["teacher_count"] == 1

    detail = await manager_client.get(
        f"/api/v1/manager/groups/{classes.group_id}",
        headers=manager_auth_headers,
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["class_detail"]["id"] == classes.id
    assert payload["binds"][0]["channel_id"] == f"manager-group-{suffix}"
    assert payload["teachers"][0]["user"]["id"] == teacher_user.id


async def test_manager_user_delete_returns_structured_blockers(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
):
    from utils.models import Classes, Teacher, User

    suffix = uuid4().hex[:8]
    creator = await User.create_user(nickname="班级创建者", username=f"manager_class_creator_{suffix}")
    teacher_user = await User.create_user(nickname="待删教师", username=f"manager_teacher_delete_{suffix}")
    teacher = await Teacher.create_teacher("待删教师", teacher_user)
    classes = await Classes.create_classes(
        name=f"删除校验班级_{suffix}",
        platform_name="QQ",
        platform_id="qq.qq_api",
        channel_id=f"manager-delete-{suffix}",
        guild_id=None,
        user=creator,
    )
    await classes.bind_teacher(teacher)

    response = await manager_client.delete(
        f"/api/v1/manager/users/{teacher_user.id}",
        headers=manager_auth_headers,
    )
    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "user_delete_blocked"
    assert any(item["code"] == "teacher_has_classes" for item in detail["blockers"])


async def test_manager_nonebot_runtime_inventory(manager_client, manager_auth_headers):
    unauthorized = await manager_client.get("/api/v1/manager/nonebot")
    assert unauthorized.status_code == 401

    response = await manager_client.get("/api/v1/manager/nonebot", headers=manager_auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["runtime"]["initialized"] is True
    assert payload["stats"]["commands"] >= 1
    assert payload["stats"]["adapters"] >= 3
    assert {"plugins", "commands", "adapters", "bots"}.issubset(payload)

    command_names = {item["command"] for item in payload["commands"]}
    assert {"token", "我的信息"}.issubset(command_names)

    adapter_modules = {item["module_name"] for item in payload["adapters"]}
    assert {
        "nonebot.adapters.onebot.v11",
        "nonebot.adapters.onebot.v12",
        "nonebot.adapters.qq",
    }.issubset(adapter_modules)

    commands = await manager_client.get("/api/v1/manager/nonebot/commands", headers=manager_auth_headers)
    assert commands.status_code == 200, commands.text
    assert commands.json()["total"] == payload["stats"]["commands"]


async def test_manager_checkpoint_delete_returns_404_when_missing(
    manager_client,
    manager_auth_headers,
    manager_workflow_tables,
):
    response = await manager_client.delete("/api/v1/manager/agents/checkpoints/999", headers=manager_auth_headers)
    assert response.status_code == 404


async def test_manager_checkpoint_crud(manager_client, manager_auth_headers, seeded_manager_checkpoint):
    detail = await manager_client.get("/api/v1/manager/agents/checkpoints/88", headers=manager_auth_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["trace_id"] == "trace-manager-88"

    listing = await manager_client.get(
        "/api/v1/manager/agents/checkpoints",
        headers=manager_auth_headers,
        params={"status": "needs_confirm"},
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1

    deleted = await manager_client.delete("/api/v1/manager/agents/checkpoints/88", headers=manager_auth_headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "user_id": 88}
