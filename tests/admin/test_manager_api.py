import os
import sys
from uuid import uuid4
from pathlib import Path
from datetime import datetime

import httpx
import pytest
import nonebot
import pytest_asyncio
from dotenv import dotenv_values
from sqlalchemy import Table, Column, String, Boolean, Integer, MetaData, ForeignKey, delete

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
    import src.interfaces.http.path  # noqa: F401

    return nonebot.get_app()


@pytest_asyncio.fixture
async def manager_client(manager_app):
    transport = httpx.ASGITransport(app=manager_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(autouse=True)
def reset_manager_tokens():
    from src.interfaces.http.managers.security import token_store

    token_store.rotate_startup_token(log_token=False)
    yield
    token_store._sessions.clear()  # noqa: SLF001


@pytest.fixture(autouse=True)
def isolate_manager_audit_log(monkeypatch, tmp_path):
    from src.interfaces.http.managers import audit
    from src.interfaces.http.managers.runtime import operations

    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", tmp_path / "manager_audit.jsonl")
    monkeypatch.setattr(operations, "AUTOMATION_SCRIPT_PATH", tmp_path / "manager_automation_scripts.json")


@pytest.fixture(autouse=True)
def isolate_manager_command_state(monkeypatch, tmp_path):
    from src.interfaces.http.managers.runtime import command_state
    from src.platform.commands.availability import command_availability

    monkeypatch.setattr(command_state, "AVAILABILITY_STATE_PATH", tmp_path / "manager_command_availability.json")
    monkeypatch.setattr(command_state, "_STATE_LOADED", False)
    command_availability.clear()
    command_state.load_availability_state(force=True)
    yield
    command_availability.clear()
    command_state._STATE_LOADED = False  # noqa: SLF001


@pytest.fixture(autouse=True)
def isolate_manager_database_cache():
    from src.interfaces.http.managers.database import service as databases

    databases.clear_database_metadata_cache()
    yield
    databases.clear_database_metadata_cache()


@pytest.fixture
def isolated_agent_designer(monkeypatch, tmp_path):
    from src.core.agent.runtime import orchestration_config
    from src.interfaces.http.managers.agent import service as agents

    designer_path = tmp_path / "agent_designer.json"
    runtime_path = tmp_path / "agent_orchestration_runtime.json"
    runtime_store = orchestration_config.RuntimeOrchestrationStore(runtime_path)

    monkeypatch.setattr(agents, "DESIGNER_CONFIG_PATH", designer_path)
    monkeypatch.setattr(agents, "AGENT_ORCHESTRATION_CONFIG_PATH", runtime_path)
    monkeypatch.setattr(orchestration_config, "AGENT_ORCHESTRATION_CONFIG_PATH", runtime_path)
    monkeypatch.setattr(orchestration_config, "runtime_orchestration_store", runtime_store)
    return {"designer_path": designer_path, "runtime_path": runtime_path}


@pytest.fixture
def manager_storage(monkeypatch, tmp_path):
    from src.core.storage import StorageManager
    import src.models.models as model_definitions
    from src.interfaces.http.managers.storage import files as manager_files
    from src.interfaces.http.managers.identity import groups as manager_groups
    from src.interfaces.http.managers.storage import chat_history as manager_chat_history

    isolated_storage = StorageManager(root=tmp_path / "storage")
    monkeypatch.setattr(manager_files, "storage_manager", isolated_storage)
    monkeypatch.setattr(manager_chat_history, "storage_manager", isolated_storage)
    monkeypatch.setattr(manager_groups, "storage_manager", isolated_storage)
    monkeypatch.setattr(model_definitions, "storage_manager", isolated_storage)
    return isolated_storage


@pytest_asyncio.fixture
async def manager_auth_headers(manager_client):
    from src.interfaces.http.managers.security import token_store

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
    from src.models import AgentWorkflowRun, AgentWorkflowCheckpoint

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
    from src.models import AgentWorkflowCheckpoint

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
    from src.interfaces.http.managers.security import token_store

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
    assert "mcp_enabled" in payload["ai"]
    assert payload["ai"]["mcp_server_url"].endswith("/mcp")
    assert payload["ai"]["mcp_transport"] in {"streamable_http", "sse"}

    invalid = await manager_client.patch(
        "/api/v1/manager/settings",
        headers=manager_auth_headers,
        json={"base": {"unsupported": True}},
    )
    assert invalid.status_code == 400
    assert "Unsupported setting keys" in invalid.json()["detail"]


async def test_manager_settings_update_writes_temp_env(manager_client, manager_auth_headers, monkeypatch, tmp_path):
    from src.interfaces.http.managers.runtime import settings as settings_store

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


async def test_manager_integrations_returns_mcp_status(manager_client, manager_auth_headers, monkeypatch):
    from src.core.mcp.schema import MCPHealthStatus
    from src.interfaces.http.managers.runtime import status as status_store

    class FakeMCPClient:
        async def health_check(self):
            return MCPHealthStatus(
                status="ok",
                enabled=True,
                server_url="http://127.0.0.1:8000/mcp",
                transport="streamable_http",
                tool_count=1,
                tools=["search_docs"],
                message="MCP Client 已连接。",
            )

    monkeypatch.setattr(status_store, "MCPClient", FakeMCPClient)

    response = await manager_client.get("/api/v1/manager/integrations", headers=manager_auth_headers)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mcp"]["status"] == "ok"
    assert payload["mcp"]["tool_count"] == 1
    assert payload["mcp"]["tools"] == ["search_docs"]


async def test_manager_runtime_config_snapshot_reads_driver_config(manager_client, manager_auth_headers, monkeypatch):
    from src.interfaces.http.managers.runtime import settings as settings_store

    class DummyConfig:
        def dict(self):
            return {
                "global_proxy": "http://127.0.0.1:7890",
                "cos_secret_key": "secret-value-for-copy",
                "empty_value": "",
                "llm_configs": [{"name": "primary", "model": "gpt-test"}],
            }

    class DummyDriver:
        config = DummyConfig()

    monkeypatch.setattr(settings_store, "driver", DummyDriver())

    response = await manager_client.get("/api/v1/manager/settings/runtime-config", headers=manager_auth_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["driver"] == "DummyDriver"
    assert payload["config_model"] == "DummyConfig"
    assert payload["total"] == 4
    assert payload["sensitive_total"] == 1

    items = {item["key"]: item for item in payload["items"]}
    assert items["global_proxy"]["value"] == "http://127.0.0.1:7890"
    assert items["global_proxy"]["value_type"] == "string"
    assert items["cos_secret_key"]["value"] == "secret-value-for-copy"
    assert items["cos_secret_key"]["masked_value"] != "secret-value-for-copy"
    assert items["cos_secret_key"]["sensitive"] is True
    assert items["empty_value"]["empty"] is True
    assert '"primary"' in items["llm_configs"]["value"]
    assert items["llm_configs"]["value_type"] == "list"


async def test_manager_models_validate_payload(manager_client, manager_auth_headers, monkeypatch, tmp_path):
    from src.interfaces.http.managers.runtime import settings as settings_store

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


async def test_manager_models_save_proxy_field(manager_client, manager_auth_headers, monkeypatch, tmp_path):
    from src.interfaces.http.managers.runtime import settings as settings_store

    env_path = tmp_path / ".env"
    monkeypatch.setattr(settings_store, "ENV_PATH", env_path)

    response = await manager_client.put(
        "/api/v1/manager/models",
        headers=manager_auth_headers,
        json={
            "llm_configs": [
                {
                    "name": "gemini_proxy",
                    "key": "sk-gemini",
                    "url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    "model": "gemini-2.5-flash",
                    "proxy": "http://127.0.0.1:7890",
                    "priority": 90,
                    "tasks": ["chat", "tool", "vision"],
                    "multi_modal": True,
                    "supports_functools": True,
                }
            ]
        },
    )
    assert response.status_code == 200, response.text

    saved_env = dotenv_values(env_path)
    assert "gemini_proxy" in saved_env["llm_configs"]
    assert "http://127.0.0.1:7890" in saved_env["llm_configs"]

    invalid_proxy = await manager_client.put(
        "/api/v1/manager/models",
        headers=manager_auth_headers,
        json={
            "llm_configs": [
                {
                    "name": "bad_proxy",
                    "key": "sk-invalid",
                    "url": "https://api.example.com/v1",
                    "model": "gpt-test",
                    "proxy": "127.0.0.1:7890",
                }
            ]
        },
    )
    assert invalid_proxy.status_code == 400
    assert "models.llm_configs[0].proxy" in invalid_proxy.json()["detail"]


async def test_manager_prompts_validate_update_and_reject_invalid_name(
    manager_client,
    manager_auth_headers,
    monkeypatch,
    tmp_path,
):
    from src.interfaces.http.managers.catalog import prompts

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
    from src.interfaces.http.managers.catalog.prompts import _safe_prompt_path

    with pytest.raises(ValueError):
        _safe_prompt_path("..\\secret")


async def test_manager_logs_limit_access_to_allowed_roots(manager_client, manager_auth_headers, monkeypatch, tmp_path):
    from src.interfaces.http.managers.runtime import logs

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
    from src.interfaces.http.managers.runtime import operations

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


async def test_manager_database_catalog_refresh_bypasses_cached_table_list(
    manager_client,
    manager_auth_headers,
    manager_database_tables,
):
    from nonebot_plugin_orm import get_session

    suffix = uuid4().hex[:8]
    table_name = f"manager_db_refresh_{suffix}"
    metadata = MetaData()
    late_table = Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String(64), nullable=False),
    )

    initial_tables = await manager_client.get("/api/v1/manager/databases/primary/tables", headers=manager_auth_headers)
    assert initial_tables.status_code == 200, initial_tables.text
    initial_names = {item["name"] for item in initial_tables.json()["items"]}
    assert table_name not in initial_names

    async with get_session() as session:
        bind = session.bind
        assert bind is not None

    try:
        async with bind.begin() as connection:
            await connection.run_sync(metadata.create_all)
            await connection.execute(late_table.insert(), {"id": 1, "name": "late-table"})

        cached_schema = await manager_client.get(
            "/api/v1/manager/databases/primary/schema", headers=manager_auth_headers
        )
        assert cached_schema.status_code == 200, cached_schema.text
        cached_names = {item["name"] for item in cached_schema.json()["tables"]}
        assert table_name not in cached_names

        cached_tables = await manager_client.get(
            "/api/v1/manager/databases/primary/tables", headers=manager_auth_headers
        )
        assert cached_tables.status_code == 200, cached_tables.text
        cached_table_names = {item["name"] for item in cached_tables.json()["items"]}
        assert table_name not in cached_table_names

        refreshed_schema = await manager_client.get(
            "/api/v1/manager/databases/primary/schema",
            headers=manager_auth_headers,
            params={"refresh": True},
        )
        assert refreshed_schema.status_code == 200, refreshed_schema.text
        refreshed_names = {item["name"] for item in refreshed_schema.json()["tables"]}
        assert table_name in refreshed_names

        refreshed_tables = await manager_client.get(
            "/api/v1/manager/databases/primary/tables", headers=manager_auth_headers
        )
        assert refreshed_tables.status_code == 200, refreshed_tables.text
        refreshed_table = next(item for item in refreshed_tables.json()["items"] if item["name"] == table_name)
        assert refreshed_table["row_count"] == 1
        assert refreshed_table["primary_key"] == ["id"]
    finally:
        async with bind.begin() as connection:
            await connection.run_sync(metadata.drop_all)


async def test_manager_user_delete_removes_user_and_binds(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
    manager_storage,
):
    from src.models import User, UserBind

    suffix = uuid4().hex[:8]
    user = await User.create_user(nickname="待删用户", username=f"manager_delete_user_{suffix}")
    await UserBind.bind_user("qq.qq_api", f"manager-delete-{suffix}", user)
    user_space = manager_storage.user_space(user.id)
    user_space.touch("documents/account.txt")
    user_space.chat_dir.joinpath("messages.db").write_text("manager delete user chat", encoding="utf-8")

    response = await manager_client.delete(f"/api/v1/manager/users/{user.id}", headers=manager_auth_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": True, "user_id": user.id}
    assert await User.filter(id=user.id).first() is None
    assert await UserBind.filter(user_id=user.id).count() == 0
    assert not user_space.space_root.exists()


async def test_manager_users_include_avatar_in_summary_and_detail(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
):
    from src.models import User

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
    from src.models import User, Classes, Teacher

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


async def test_manager_group_delete_cleans_related_storage_and_records(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
    manager_storage,
):
    from src.models import User, Group, Classes, GroupBind

    suffix = uuid4().hex[:8]
    creator = await User.create_user(nickname="群删除创建者", username=f"manager_group_delete_creator_{suffix}")
    channel_owner_id = f"manager-group-delete-{suffix}"
    classes = await Classes.create_classes(
        name=f"删除群组班级_{suffix}",
        platform_name="QQ",
        platform_id="qq.qq_api",
        channel_id=channel_owner_id,
        guild_id=None,
        user=creator,
    )

    group_space = manager_storage.group_space(classes.group_id)
    group_space.touch("documents/readme.txt")
    group_space.resolve("documents/readme.txt", reject_escape=True).path.write_text("group delete", "utf-8")
    bound_group_space = manager_storage.group_space(channel_owner_id)
    bound_group_space.touch("documents/channel.txt")
    bound_group_space.resolve("documents/channel.txt", reject_escape=True).path.write_text("channel delete", "utf-8")

    response = await manager_client.delete(
        f"/api/v1/manager/groups/{classes.group_id}",
        headers=manager_auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["group_id"] == classes.group_id

    assert await Group.filter(id=classes.group_id).first() is None
    assert await Classes.filter(id=classes.id).first() is None
    assert await GroupBind.filter(group_id=classes.group_id).count() == 0
    assert not group_space.space_root.exists()
    assert not bound_group_space.space_root.exists()


async def test_manager_user_delete_returns_structured_blockers(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
):
    from src.models import User, Classes, Teacher

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
    from src.platform.commands import CommandSpec, command_registry

    command_registry.register(
        CommandSpec(
            name="测试管理端无Handler命令",
            description="声明为 service 但没有注册 handler",
            execution_mode="service",
            agent_callable=True,
        )
    )

    unauthorized = await manager_client.get("/api/v1/manager/nonebot")
    assert unauthorized.status_code == 401

    response = await manager_client.get("/api/v1/manager/nonebot", headers=manager_auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["runtime"]["initialized"] is True
    assert payload["stats"]["commands"] >= 1
    assert payload["stats"]["adapters"] >= 3
    assert payload["stats"]["service_handler_commands"] >= 1
    assert payload["stats"]["agent_executable_commands"] >= 1
    assert {"plugins", "commands", "adapters", "bots"}.issubset(payload)

    command_names = {item["command"] for item in payload["commands"]}
    assert {"token", "我的信息"}.issubset(command_names)
    chat_statistics = next(item for item in payload["commands"] if item["command"] == "统计聊天记录")
    assert chat_statistics["matcher_type"] == "agent_command"
    assert (
        chat_statistics["file"]
        .replace("\\", "/")
        .endswith("src/plugins/application/active/message_history/commands.py")
    )
    assert chat_statistics["line"] > 0
    assert chat_statistics["service_handler_registered"] is True
    assert chat_statistics["agent_executable"] is True
    assert all(param["required"] is False for param in chat_statistics["params"])

    command_without_handler = next(item for item in payload["commands"] if item["command"] == "测试管理端无Handler命令")
    assert command_without_handler["agent_callable"] is True
    assert command_without_handler["execution_mode"] == "service"
    assert command_without_handler["service_handler_registered"] is False
    assert command_without_handler["agent_executable"] is False

    adapter_modules = {item["module_name"] for item in payload["adapters"]}
    assert {
        "nonebot.adapters.onebot.v11",
        "nonebot.adapters.onebot.v12",
        "nonebot.adapters.qq",
    }.issubset(adapter_modules)

    commands = await manager_client.get("/api/v1/manager/nonebot/commands", headers=manager_auth_headers)
    assert commands.status_code == 200, commands.text
    assert commands.json()["total"] == payload["stats"]["commands"]
    command_payload = next(item for item in commands.json()["items"] if item["command"] == "统计聊天记录")
    assert command_payload["agent_executable"] is True


async def test_manager_nonebot_availability_controls(manager_client, manager_auth_headers):
    command_update = await manager_client.patch(
        "/api/v1/manager/nonebot/commands/pwd/availability",
        headers=manager_auth_headers,
        json={"enabled": False, "reason": "maintenance"},
    )
    assert command_update.status_code == 200, command_update.text
    assert command_update.json()["enabled"] is False
    assert command_update.json()["reason"] == "maintenance"

    availability = await manager_client.get("/api/v1/manager/nonebot/availability", headers=manager_auth_headers)
    assert availability.status_code == 200, availability.text
    assert availability.json()["commands"]["pwd"]["enabled"] is False

    overview = await manager_client.get("/api/v1/manager/nonebot", headers=manager_auth_headers)
    assert overview.status_code == 200, overview.text
    pwd_command = next(item for item in overview.json()["commands"] if item["command"] == "pwd")
    assert pwd_command["available"] is False
    assert pwd_command["availability_reason"] == "maintenance"

    plugin_update = await manager_client.patch(
        "/api/v1/manager/nonebot/plugins/src.plugins.application.active.file_manager/availability",
        headers=manager_auth_headers,
        json={"enabled": False, "reason": "plugin-disabled"},
    )
    assert plugin_update.status_code == 200, plugin_update.text
    assert plugin_update.json()["enabled"] is False

    plugin_listing = await manager_client.get("/api/v1/manager/nonebot/plugins", headers=manager_auth_headers)
    assert plugin_listing.status_code == 200, plugin_listing.text
    file_manager_plugin = next(
        item
        for item in plugin_listing.json()["items"]
        if item["module_name"] == "src.plugins.application.active.file_manager"
    )
    assert file_manager_plugin["available"] is False
    assert file_manager_plugin["availability_reason"] == "plugin-disabled"


async def test_manager_file_space_management_api(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
    manager_storage,
):
    from src.models import User, Classes

    suffix = uuid4().hex[:8]
    user = await User.create_user(nickname="文件用户", username=f"manager_file_user_{suffix}")
    creator = await User.create_user(nickname="文件群创建者", username=f"manager_file_group_{suffix}")
    group_channel_id = f"manager-files-{suffix}"
    classes = await Classes.create_classes(
        name=f"文件测试班级_{suffix}",
        platform_name="QQ",
        platform_id="qq.qq_api",
        channel_id=group_channel_id,
        guild_id=None,
        user=creator,
    )

    user_space = manager_storage.user_space(user.id)
    group_space = manager_storage.group_space(classes.group_id)

    user_space.touch("documents/readme.txt")
    user_space.resolve("documents/readme.txt", reject_escape=True).path.write_text("hello user space", "utf-8")
    group_space.touch("images/group-note.txt")
    group_space.resolve("images/group-note.txt", reject_escape=True).path.write_text("hello group space", "utf-8")

    spaces = await manager_client.get("/api/v1/manager/files/spaces", headers=manager_auth_headers)
    assert spaces.status_code == 200, spaces.text
    space_items = spaces.json()["items"]
    user_item = next(item for item in space_items if item["kind"] == "user" and item["owner_id"] == str(user.id))
    group_item = next(
        item for item in space_items if item["kind"] == "group" and item["owner_id"] == str(classes.group_id)
    )
    assert user_item["linked"] is True
    assert group_item["title"] == f"文件测试班级_{suffix}"
    assert group_item["owner"]["group_id"] == classes.group_id
    assert group_item["owner"]["channel_ids"] == [group_channel_id]
    assert not manager_storage.space_root("group", group_channel_id).exists()

    detail = await manager_client.get(
        f"/api/v1/manager/files/spaces/user/{user.id}",
        headers=manager_auth_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["cwd"] == "~"

    entries = await manager_client.get(
        f"/api/v1/manager/files/spaces/user/{user.id}/entries",
        headers=manager_auth_headers,
        params={"path": "documents"},
    )
    assert entries.status_code == 200, entries.text
    assert any(item["name"] == "readme.txt" for item in entries.json()["items"])

    preview = await manager_client.get(
        f"/api/v1/manager/files/spaces/user/{user.id}/read",
        headers=manager_auth_headers,
        params={"path": "documents/readme.txt"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["content"] == "hello user space"

    mkdir = await manager_client.post(
        f"/api/v1/manager/files/spaces/user/{user.id}/directories",
        headers=manager_auth_headers,
        json={"path": "documents/generated"},
    )
    assert mkdir.status_code == 200, mkdir.text
    assert mkdir.json()["created"] is True

    write = await manager_client.put(
        f"/api/v1/manager/files/spaces/user/{user.id}/write",
        headers=manager_auth_headers,
        json={"path": "documents/readme.txt", "content": "updated by manager"},
    )
    assert write.status_code == 200, write.text
    assert write.json()["saved"] is True

    preview_after_write = await manager_client.get(
        f"/api/v1/manager/files/spaces/user/{user.id}/read",
        headers=manager_auth_headers,
        params={"path": "documents/readme.txt"},
    )
    assert preview_after_write.status_code == 200, preview_after_write.text
    assert preview_after_write.json()["content"] == "updated by manager"

    delete_file = await manager_client.delete(
        f"/api/v1/manager/files/spaces/user/{user.id}/entry",
        headers=manager_auth_headers,
        params={"path": "documents/readme.txt"},
    )
    assert delete_file.status_code == 200, delete_file.text
    assert delete_file.json()["deleted"] is True

    delete_dir = await manager_client.delete(
        f"/api/v1/manager/files/spaces/user/{user.id}/entry",
        headers=manager_auth_headers,
        params={"path": "documents/generated", "recursive": True},
    )
    assert delete_dir.status_code == 200, delete_dir.text
    assert delete_dir.json()["deleted"] is True

    traversal = await manager_client.get(
        f"/api/v1/manager/files/spaces/user/{user.id}/entries",
        headers=manager_auth_headers,
        params={"path": "../"},
    )
    assert traversal.status_code == 400


async def test_manager_file_space_delete_entire_space(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
    manager_storage,
):
    from src.models import User

    suffix = uuid4().hex[:8]
    user = await User.create_user(nickname="文件删除用户", username=f"manager_file_delete_{suffix}")
    user_space = manager_storage.user_space(user.id)
    user_space.touch("documents/readme.txt")
    user_space.resolve("documents/readme.txt", reject_escape=True).path.write_text("delete all", "utf-8")

    response = await manager_client.delete(
        f"/api/v1/manager/files/spaces/user/{user.id}",
        headers=manager_auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["kind"] == "user"
    assert payload["owner_id"] == str(user.id)
    assert not user_space.space_root.exists()


async def test_manager_chat_history_management_api(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
    manager_storage,
):
    from src.models import User, Classes
    from src.core.storage import ChatHistoryStore, MessageActorRole

    suffix = uuid4().hex[:8]
    private_user = await User.create_user(nickname="聊天用户", username=f"manager_chat_user_{suffix}")
    creator = await User.create_user(nickname="聊天群创建者", username=f"manager_chat_group_{suffix}")
    classes = await Classes.create_classes(
        name=f"聊天记录班级_{suffix}",
        platform_name="QQ",
        platform_id="qq.qq_api",
        channel_id=f"manager-chat-{suffix}",
        guild_id=None,
        user=creator,
    )

    store = ChatHistoryStore(manager_storage)
    await store.record_user_chat_message(
        user_id=private_user.id,
        user_name=private_user.nickname,
        plain_text="我想查询奖学金申请进度",
        raw_text="我想查询奖学金申请进度",
        actor_role=MessageActorRole.user,
        message_id="pm-user-1",
        platform="onebot11.qq_client",
        platform_name="QQ",
        bot_id="114514",
        platform_user_id="manager-user-platform",
        metadata={"source": "manager_api_test", "scene": "private_inbound"},
        created_at=datetime(2026, 5, 1, 9, 15, 0),
    )
    await store.record_user_chat_message(
        user_id=private_user.id,
        user_name=private_user.nickname,
        actor_id="assistant",
        actor_name="ClassRobot",
        plain_text="奖学金申请还在审核中",
        raw_text="奖学金申请还在审核中",
        actor_role=MessageActorRole.assistant,
        message_id="pm-assistant-1",
        platform="onebot11.qq_client",
        platform_name="QQ",
        bot_id="114514",
        platform_user_id="114514",
        metadata={"source": "manager_api_test", "scene": "private_outbound"},
        created_at=datetime(2026, 5, 2, 10, 45, 0),
    )
    await store.record_group_collect_message(
        group_id=classes.group_id,
        user_id="u1",
        user_name="张三",
        plain_text="今天班会调课吗",
        raw_text="今天班会调课吗",
        message_id="gm-1",
        platform="qq.qq_api",
        platform_name="QQ",
        channel_id=f"manager-chat-{suffix}",
        bot_id="114514",
        platform_user_id="u1",
        metadata={"source": "manager_api_test", "scene": "group_collect"},
        created_at=datetime(2026, 5, 3, 8, 30, 0),
    )
    await store.record_group_collect_message(
        group_id=classes.group_id,
        user_id="u2",
        user_name="李四",
        plain_text="调课通知已经发了吗",
        raw_text="调课通知已经发了吗",
        message_id="gm-2",
        platform="qq.qq_api",
        platform_name="QQ",
        channel_id=f"manager-chat-{suffix}",
        bot_id="114514",
        platform_user_id="u2",
        metadata={"source": "manager_api_test", "scene": "group_collect"},
        created_at=datetime(2026, 5, 3, 9, 5, 0),
    )

    spaces = await manager_client.get("/api/v1/manager/chat-history/spaces", headers=manager_auth_headers)
    assert spaces.status_code == 200, spaces.text
    items = spaces.json()["items"]

    user_item = next(item for item in items if item["kind"] == "user" and item["owner_id"] == str(private_user.id))
    group_item = next(item for item in items if item["kind"] == "group" and item["owner_id"] == str(classes.group_id))

    assert user_item["linked"] is True
    assert user_item["message_count"] == 2
    assert user_item["actor_counts"]["assistant"] == 1
    assert user_item["direction_counts"]["inbound"] == 1
    assert user_item["direction_counts"]["outbound"] == 1
    assert group_item["title"] == f"聊天记录班级_{suffix}"
    assert group_item["record_counts"]["collect"] == 2
    assert f"manager-chat-{suffix}" in group_item["owner"]["channels"]

    detail = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/user/{private_user.id}",
        headers=manager_auth_headers,
    )
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["message_count"] == 2
    assert detail_payload["latest_message_preview"] == "奖学金申请还在审核中"

    default_messages = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/user/{private_user.id}/messages",
        headers=manager_auth_headers,
    )
    assert default_messages.status_code == 200, default_messages.text
    default_payload = default_messages.json()
    assert default_payload["message_date"] == "2026-05-02"
    assert default_payload["available_dates"] == ["2026-05-02", "2026-05-01"]
    assert default_payload["total"] == 1
    assert default_payload["items"][0]["message_id"] == "pm-assistant-1"

    assistant_messages = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/user/{private_user.id}/messages",
        headers=manager_auth_headers,
        params={"actor_role": "assistant", "direction": "outbound"},
    )
    assert assistant_messages.status_code == 200, assistant_messages.text
    assistant_payload = assistant_messages.json()
    assert assistant_payload["total"] == 1
    assert assistant_payload["message_date"] == "2026-05-02"
    assert assistant_payload["available_dates"] == ["2026-05-02"]
    assert assistant_payload["items"][0]["user_name"] == "ClassRobot"
    assert assistant_payload["items"][0]["record_kind"] == "chat"
    assert assistant_payload["items"][0]["direction"] == "outbound"
    assert assistant_payload["items"][0]["owner_kind"] == "user"
    assert assistant_payload["items"][0]["owner_id"] == str(private_user.id)
    assert assistant_payload["items"][0]["platform"] == "onebot11.qq_client"
    assert assistant_payload["items"][0]["bot_id"] == "114514"
    assert assistant_payload["items"][0]["metadata"]["scene"] == "private_outbound"

    group_messages = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/group/{classes.group_id}/messages",
        headers=manager_auth_headers,
        params={"record_kind": "collect", "q": "调课"},
    )
    assert group_messages.status_code == 200, group_messages.text
    group_payload = group_messages.json()
    assert group_payload["message_date"] == "2026-05-03"
    assert group_payload["available_dates"] == ["2026-05-03"]
    assert group_payload["total"] == 2
    assert group_payload["items"][0]["user_name"] in {"张三", "李四"}
    assert group_payload["items"][0]["channel_id"] == f"manager-chat-{suffix}"
    assert group_payload["items"][0]["direction"] == "inbound"

    dated_messages = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/user/{private_user.id}/messages",
        headers=manager_auth_headers,
        params={"message_date": "2026-05-01"},
    )
    assert dated_messages.status_code == 200, dated_messages.text
    dated_payload = dated_messages.json()
    assert dated_payload["message_date"] == "2026-05-01"
    assert dated_payload["available_dates"] == ["2026-05-02", "2026-05-01"]
    assert dated_payload["total"] == 1
    assert dated_payload["items"][0]["message_id"] == "pm-user-1"
    assert dated_payload["items"][0]["direction"] == "inbound"

    fallback_messages = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/user/{private_user.id}/messages",
        headers=manager_auth_headers,
        params={"message_date": "2026-05-06"},
    )
    assert fallback_messages.status_code == 200, fallback_messages.text
    fallback_payload = fallback_messages.json()
    assert fallback_payload["message_date"] == "2026-05-02"
    assert fallback_payload["available_dates"] == ["2026-05-02", "2026-05-01"]
    assert fallback_payload["total"] == 1
    assert fallback_payload["items"][0]["message_id"] == "pm-assistant-1"

    invalid_filter = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/group/{classes.group_id}/messages",
        headers=manager_auth_headers,
        params={"record_kind": "unknown"},
    )
    assert invalid_filter.status_code == 400

    invalid_direction = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/group/{classes.group_id}/messages",
        headers=manager_auth_headers,
        params={"direction": "sideways"},
    )
    assert invalid_direction.status_code == 400

    invalid_date = await manager_client.get(
        f"/api/v1/manager/chat-history/spaces/group/{classes.group_id}/messages",
        headers=manager_auth_headers,
        params={"message_date": "2026/05/03"},
    )
    assert invalid_date.status_code == 400


async def test_manager_chat_history_delete_space(
    manager_client,
    manager_auth_headers,
    manager_user_orm,
    manager_storage,
):
    from src.models import User
    from src.core.storage import ChatHistoryStore, MessageActorRole

    suffix = uuid4().hex[:8]
    private_user = await User.create_user(nickname="聊天删除用户", username=f"manager_chat_delete_{suffix}")

    store = ChatHistoryStore(manager_storage)
    await store.record_user_chat_message(
        user_id=private_user.id,
        user_name=private_user.nickname,
        plain_text="删除前消息",
        raw_text="删除前消息",
        actor_role=MessageActorRole.user,
        message_id="pm-delete-1",
        platform="onebot11.qq_client",
        platform_name="QQ",
        bot_id="114514",
        platform_user_id="delete-user-platform",
        metadata={"source": "manager_api_test", "scene": "private_delete"},
    )

    chat_db_path = manager_storage.user_space(private_user.id).chat_dir / "messages.db"
    assert chat_db_path.exists()

    response = await manager_client.delete(
        f"/api/v1/manager/chat-history/spaces/user/{private_user.id}",
        headers=manager_auth_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["kind"] == "user"
    assert payload["owner_id"] == str(private_user.id)
    assert not chat_db_path.parent.exists()


async def test_manager_checkpoint_delete_returns_404_when_missing(
    manager_client,
    manager_auth_headers,
    manager_workflow_tables,
):
    response = await manager_client.delete("/api/v1/manager/agents/checkpoints/999", headers=manager_auth_headers)
    assert response.status_code == 404


async def test_manager_agent_overview_inventory(
    manager_client,
    manager_auth_headers,
    manager_workflow_tables,
    isolated_agent_designer,
):
    from src.models import AgentWorkflowRun, AgentWorkflowCheckpoint

    await AgentWorkflowRun(
        user_id=77,
        trace_id="trace-agent-overview-77",
        kind="command_sequence",
        status="failed",
        goal="测试 Agent 概览",
        summary="测试失败运行",
        workflow_data={"steps": [{"command": "测试命令"}]},
    ).create()
    await AgentWorkflowCheckpoint(
        user_id=77,
        trace_id="trace-agent-overview-77",
        kind="command_sequence",
        status="needs_confirm",
        goal="测试 Agent 概览",
        summary="等待确认",
        workflow_data={"approval": {"status": "pending"}},
    ).create()

    unauthorized = await manager_client.get("/api/v1/manager/agents/overview")
    assert unauthorized.status_code == 401

    response = await manager_client.get("/api/v1/manager/agents/overview", headers=manager_auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()

    module_ids = {item["id"] for item in payload["modules"]}
    assert {"pipeline", "workflow", "command_tools", "skill_registry"}.issubset(module_ids)
    assert payload["stats"]["failed_runs"] == 1
    assert payload["stats"]["pending_checkpoints"] == 1
    assert payload["stats"]["agent_executable_commands"] >= 1
    assert payload["metrics"]["runs_by_kind"]["command_sequence"] == 1
    assert payload["orchestration"]["nodes"][0]["id"] == "summary_history"
    assert payload["designer"]["runtime_apply_supported"] is True
    assert payload["playbooks"]
    assert payload["skills"]
    module_status = {item["id"]: item["status"] for item in payload["modules"]}
    assert module_status["checkpoint_store"] == "enabled"
    assert module_status["run_store"] == "enabled"
    assert any(item["id"] == "agent_module_toggle" and item["supported"] is False for item in payload["controls"])
    assert any(item["id"] == "command_soft_switch" and item["supported"] is True for item in payload["controls"])
    assert any(
        item["id"] == "command_soft_switch" and item["route"] == "/nonebot/plugins" for item in payload["controls"]
    )


async def test_manager_agent_live_trace_api(manager_client, manager_auth_headers):
    from src.core.agent.runtime.live_trace import AgentLiveTraceConfig, agent_live_trace_registry

    original_config = agent_live_trace_registry.config
    agent_live_trace_registry.clear()
    agent_live_trace_registry.config = AgentLiveTraceConfig(enabled=True, max_traces=5, max_events_per_trace=20)
    try:
        agent_live_trace_registry.start_trace("trace-live-manager", user_id=9, message_preview="查一下天气")
        agent_live_trace_registry.emit(
            "trace-live-manager",
            event_type="mcp_call_started",
            stage="tool_call",
            status="running",
            tool_name="weather",
            params_preview={"authorization": "secret", "query": "北京天气"},
        )

        status_response = await manager_client.get("/api/v1/manager/agents/live/status", headers=manager_auth_headers)
        assert status_response.status_code == 200, status_response.text
        assert status_response.json()["enabled"] is True
        assert status_response.json()["active_count"] == 1

        list_response = await manager_client.get("/api/v1/manager/agents/live/traces", headers=manager_auth_headers)
        assert list_response.status_code == 200, list_response.text
        assert list_response.json()["items"][0]["trace_id"] == "trace-live-manager"

        detail_response = await manager_client.get(
            "/api/v1/manager/agents/live/traces/trace-live-manager",
            headers=manager_auth_headers,
        )
        assert detail_response.status_code == 200, detail_response.text
        payload = detail_response.json()
        assert payload["events"][1]["event_type"] == "mcp_call_started"
        assert payload["events"][1]["params_preview"]["authorization"] == "***"
    finally:
        agent_live_trace_registry.clear()
        agent_live_trace_registry.config = original_config


async def test_manager_agent_designer_draft(manager_client, manager_auth_headers, isolated_agent_designer):
    unauthorized = await manager_client.get("/api/v1/manager/agents/designer")
    assert unauthorized.status_code == 401

    detail = await manager_client.get("/api/v1/manager/agents/designer", headers=manager_auth_headers)
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["capabilities"]["draft_orchestration_supported"] is True
    assert payload["capabilities"]["runtime_apply_supported"] is True
    assert payload["runtime"]["enabled"] is True
    assert payload["runtime"]["mode"] == "graph"
    assert payload["draft"]["nodes"]
    assert payload["draft"]["nodes"][0]["node_type"] == "summary_history"
    assert payload["applied_to_runtime"] is True
    assert payload["draft"]["nodes"][0]["runtime_applied"] is True
    assert all(item["status"] == "enabled" for item in payload["palette"])

    draft = payload["draft"]
    draft["nodes"][0]["config"] = {"model": "default", "temperature": 0.2, "unknown": "ignored"}
    saved = await manager_client.put(
        "/api/v1/manager/agents/designer",
        headers=manager_auth_headers,
        json={
            "nodes": draft["nodes"],
            "edges": draft["edges"],
            "note": "测试草稿",
        },
    )
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["saved"] is True
    assert body["applied_to_runtime"] is False
    saved_draft = body["designer"]["draft"]
    assert saved_draft["nodes"][0]["config"] == {"model": "default", "temperature": 0.2}
    assert saved_draft["edges"][0]["source"] == "summary_history"
    assert not isolated_agent_designer["runtime_path"].exists()

    invalid = await manager_client.put(
        "/api/v1/manager/agents/designer",
        headers=manager_auth_headers,
        json={
            "nodes": [{"id": "bad-node", "node_type": "unknown-node", "module_id": "pipeline"}],
            "edges": [],
        },
    )
    assert invalid.status_code == 400


async def test_manager_agent_designer_apply_hot_reload(manager_client, manager_auth_headers, isolated_agent_designer):
    from src.core.agent.runtime.orchestration_config import get_runtime_orchestration_snapshot

    detail = await manager_client.get("/api/v1/manager/agents/designer", headers=manager_auth_headers)
    assert detail.status_code == 200, detail.text
    draft = detail.json()["draft"]

    applied = await manager_client.put(
        "/api/v1/manager/agents/designer",
        headers=manager_auth_headers,
        json={
            "nodes": draft["nodes"],
            "edges": draft["edges"],
            "note": "测试热更新",
            "apply_to_runtime": True,
        },
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["saved"] is True
    assert body["applied_to_runtime"] is True
    assert body["restart_required"] is False
    assert body["designer"]["applied_to_runtime"] is True
    assert body["designer"]["runtime"]["enabled"] is True
    assert isolated_agent_designer["runtime_path"].exists()

    snapshot = get_runtime_orchestration_snapshot()
    assert snapshot.graph_enabled is True
    assert snapshot.config.mode == "graph"
    assert snapshot.config.node_order[0] == "summary_history"
    assert snapshot.config.node_order[-1] == "persist"

    invalid_apply = await manager_client.put(
        "/api/v1/manager/agents/designer",
        headers=manager_auth_headers,
        json={
            "nodes": [
                {
                    "id": "normalize_input",
                    "node_type": "normalize_input",
                    "module_id": "pipeline",
                    "label": "NormalizeUserInput",
                    "phase": "输入",
                },
                {
                    "id": "append_user_message",
                    "node_type": "append_user_message",
                    "module_id": "pipeline",
                    "label": "AppendUserMessage",
                    "phase": "会话",
                },
            ],
            "edges": [
                {
                    "id": "normalize_input__append_user_message",
                    "source": "normalize_input",
                    "target": "append_user_message",
                }
            ],
            "apply_to_runtime": True,
        },
    )
    assert invalid_apply.status_code == 400
    assert "missing required nodes" in invalid_apply.json()["detail"]


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
