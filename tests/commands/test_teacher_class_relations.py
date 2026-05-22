from __future__ import annotations

from importlib import import_module

import pytest
import sqlalchemy as sa


def create_teacher_classes_table(connection) -> None:
    """创建迁移 SQL 所需的最小教师-班级关系表。"""

    connection.execute(
        sa.text(
            """
            CREATE TABLE bot_teacher_classes (
                id INTEGER PRIMARY KEY,
                teacher_id INTEGER NOT NULL,
                classes_id INTEGER NOT NULL,
                role VARCHAR(32) NOT NULL
            )
            """
        )
    )


def test_teacher_classes_migration_keeps_highest_priority_role() -> None:
    """重复关系去重时应保留班主任/辅导员，不能静默保留普通任课老师。"""

    migration = import_module("migrations.versions.b2f4d8a7c6e1_add_college_teacher_roles")
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        create_teacher_classes_table(connection)
        connection.execute(
            sa.text(
                """
                INSERT INTO bot_teacher_classes (id, teacher_id, classes_id, role)
                VALUES
                    (1, 10, 20, 'teacher'),
                    (2, 10, 20, 'homeroom'),
                    (3, 10, 20, 'counselor'),
                    (4, 11, 20, 'teacher'),
                    (5, 11, 20, 'teacher')
                """
            )
        )

        unknown_roles = connection.execute(
            sa.text(migration.unknown_duplicate_teacher_class_roles_sql())
        ).scalars().all()
        assert unknown_roles == []

        connection.execute(sa.text(migration.deduplicate_teacher_classes_sql()))
        rows = connection.execute(
            sa.text(
                """
                SELECT id, teacher_id, classes_id, role
                FROM bot_teacher_classes
                ORDER BY teacher_id, classes_id
                """
            )
        ).all()

    assert rows == [
        (2, 10, 20, "homeroom"),
        (4, 11, 20, "teacher"),
    ]


def test_teacher_classes_migration_reports_unknown_duplicate_roles() -> None:
    """重复关系里出现未知岗位时应交给人工处理，不能猜测删除。"""

    migration = import_module("migrations.versions.b2f4d8a7c6e1_add_college_teacher_roles")
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        create_teacher_classes_table(connection)
        connection.execute(
            sa.text(
                """
                INSERT INTO bot_teacher_classes (id, teacher_id, classes_id, role)
                VALUES
                    (1, 10, 20, 'teacher'),
                    (2, 10, 20, 'legacy_manager')
                """
            )
        )

        unknown_roles = connection.execute(
            sa.text(migration.unknown_duplicate_teacher_class_roles_sql())
        ).scalars().all()

    assert unknown_roles == ["legacy_manager"]


@pytest.mark.asyncio
async def test_bind_teacher_does_not_downgrade_existing_manager_role(models) -> None:
    """`bind_teacher()` 默认只保证绑定存在，不应覆盖已有班级管理岗位。"""

    from src.models import TeacherClasses
    from src.core.auth import TeacherClassesRole

    teacher_user = await models.create_user(account_id=10201, nickname="绑定老师")
    teacher = await models.create_teacher(teacher_user, name="绑定老师")
    classes = await models.create_classes(name="绑定语义班", owner=teacher_user, group_id=20201, teacher=teacher)

    relation = await TeacherClasses.filter(teacher_id=teacher.id, classes_id=classes.id).first()
    assert relation is not None
    assert relation.role == TeacherClassesRole.counselor

    await classes.bind_teacher(teacher)
    relation = await TeacherClasses.filter(teacher_id=teacher.id, classes_id=classes.id).first()
    assert relation is not None
    assert relation.role == TeacherClassesRole.counselor

    await classes.bind_teacher(teacher, role=TeacherClassesRole.teacher, update_role=True)
    relation = await TeacherClasses.filter(teacher_id=teacher.id, classes_id=classes.id).first()
    assert relation is not None
    assert relation.role == TeacherClassesRole.teacher
