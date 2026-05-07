from __future__ import annotations

import pytest
import pytest_asyncio


pytestmark = pytest.mark.asyncio


async def _recreate_model_orm_schema() -> None:
    """重建模型行为测试使用的 ORM 表结构。"""

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


@pytest_asyncio.fixture(autouse=True)
async def model_orm(loaded_plugins):
    """为每条测试重建 ORM，避免模型状态互相污染。"""

    await _recreate_model_orm_schema()
    yield


async def test_leave_workflow_order_users_returns_real_users_in_order():
    """审批顺序应返回真实用户对象，并保持配置中的先后顺序。"""

    from utils.models import Classes, Group, LeaveWorkflow, School, User

    creator = await User.create_user(nickname="创建者", username="leave_creator")
    approver_a = await User.create_user(nickname="审批人甲", username="leave_approver_a")
    approver_b = await User.create_user(nickname="审批人乙", username="leave_approver_b")
    school = await School(name="请假测试学校").create()
    group = await Group.create_group("请假测试群", creator)
    classes = await Classes(name="请假测试班级", group=group, school_id=school.id).create()
    workflow = await LeaveWorkflow(
        classes_id=classes.id,
        shool_id=school.id,
        order=[approver_b.id, approver_a.id],
    ).create()

    users = await workflow.order_users()

    assert [user.id for user in users] == [approver_b.id, approver_a.id]
    assert [user.nickname for user in users] == ["审批人乙", "审批人甲"]
