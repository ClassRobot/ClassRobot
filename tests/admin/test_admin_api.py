from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from nonebot import get_app


def _unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


async def _recreate_orm_schema() -> None:
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


@pytest.fixture(scope="session", autouse=True)
def admin_helper_runtime(loaded_plugins):
    from utils.helper.runtime import bootstrap_helper_runtime

    bootstrap_helper_runtime(loaded_plugins)
    return loaded_plugins


@pytest_asyncio.fixture(scope="session", autouse=True)
async def admin_orm(loaded_plugins):
    await _recreate_orm_schema()
    yield

    import nonebot_plugin_orm as orm

    for engine in orm._engines.values():
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def reset_admin_orm(admin_orm):
    await _recreate_orm_schema()
    yield


async def _create_user(*, is_admin: bool, password: str = "pass123"):
    from utils.models import User

    username = _unique_name("admin" if is_admin else "user")
    user = await User.create_user(
        nickname=username,
        username=username,
        password=password,
        email=f"{username}@example.com",
    )
    if is_admin:
        user = await user.update(is_admin=True)
    return user


@pytest.mark.asyncio
async def test_admin_auth_status_and_login_flow(loaded_plugins):
    app = get_app()
    assert isinstance(app, FastAPI)

    admin_user = await _create_user(is_admin=True, password="secret-admin")
    normal_user = await _create_user(is_admin=False, password="secret-user")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        status_response = await client.get("/api/v1/admin/auth/status")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["auth_mode"] == "admin-user-password"
        assert status_payload["admin_account_count"] >= 1

        forbidden_response = await client.post(
            "/api/v1/admin/auth/login",
            json={"username": normal_user.username, "password": "secret-user"},
        )
        assert forbidden_response.status_code == 403

        login_response = await client.post(
            "/api/v1/admin/auth/login",
            json={"username": admin_user.username, "password": "secret-admin"},
        )
        assert login_response.status_code == 200
        login_payload = login_response.json()
        assert login_payload["user"]["username"] == admin_user.username
        assert login_payload["token_type"] == "bearer"
        access_token = login_payload["access_token"]

        me_response = await client.get(
            "/api/v1/admin/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["id"] == admin_user.id


@pytest.mark.asyncio
async def test_admin_user_crud_and_readonly_views(loaded_plugins):
    from utils.models import User

    app = get_app()
    assert isinstance(app, FastAPI)

    admin_user = await _create_user(is_admin=True, password="secret-admin")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        login_response = await client.post(
            "/api/v1/admin/auth/login",
            json={"username": admin_user.username, "password": "secret-admin"},
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        create_payload = {
            "nickname": "后台测试用户",
            "username": _unique_name("managed"),
            "password": "pass123",
            "email": None,
            "phone": None,
            "gender": None,
            "is_admin": False,
        }
        create_response = await client.post("/api/v1/admin/users", json=create_payload, headers=headers)
        assert create_response.status_code == 201
        created_user = create_response.json()

        list_response = await client.get("/api/v1/admin/users", headers=headers)
        assert list_response.status_code == 200
        assert any(item["id"] == created_user["id"] for item in list_response.json()["items"])

        update_response = await client.patch(
            f"/api/v1/admin/users/{created_user['id']}",
            json={"nickname": "后台测试用户-已更新", "is_admin": True},
            headers=headers,
        )
        assert update_response.status_code == 200
        assert update_response.json()["nickname"] == "后台测试用户-已更新"
        assert update_response.json()["is_admin"] is True

        for path in (
            "/api/v1/admin/overview",
            "/api/v1/admin/commands",
            "/api/v1/admin/plugins",
            "/api/v1/admin/skills",
            "/api/v1/admin/models",
            "/api/v1/admin/bots",
            "/api/v1/admin/agents",
            "/api/v1/admin/database",
            "/api/v1/admin/system",
        ):
            response = await client.get(path, headers=headers)
            assert response.status_code == 200, path

        delete_response = await client.delete(f"/api/v1/admin/users/{created_user['id']}", headers=headers)
        assert delete_response.status_code == 204

        deleted_user = await User.filter(id=created_user["id"]).first()
        assert deleted_user is None
