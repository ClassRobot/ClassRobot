"""add college teacher role relation

迁移 ID: b2f4d8a7c6e1
父迁移: 9bc9d0cbf59e
创建时间: 2026-05-19 01:55:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2f4d8a7c6e1"
down_revision: str | Sequence[str] | None = "9bc9d0cbf59e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEACHER_CLASS_ROLE_PRIORITY_SQL = """
CASE role
    WHEN 'homeroom' THEN 0
    WHEN 'counselor' THEN 1
    WHEN 'teacher' THEN 2
    ELSE 99
END
"""
VALID_TEACHER_CLASS_ROLES = "'homeroom', 'counselor', 'teacher'"


def unknown_duplicate_teacher_class_roles_sql() -> str:
    """返回用于发现重复教师-班级关系中未知岗位的 SQL。"""

    return f"""
            SELECT DISTINCT role
            FROM bot_teacher_classes AS relation
            WHERE role NOT IN ({VALID_TEACHER_CLASS_ROLES})
              AND EXISTS (
                  SELECT 1
                  FROM bot_teacher_classes AS duplicated
                  WHERE duplicated.teacher_id = relation.teacher_id
                    AND duplicated.classes_id = relation.classes_id
                    AND duplicated.id != relation.id
              )
            """


def deduplicate_teacher_classes_sql() -> str:
    """返回保留最高权限教师-班级关系的去重 SQL。"""

    return f"""
        DELETE FROM bot_teacher_classes
        WHERE id IN (
            SELECT id
            FROM (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY teacher_id, classes_id
                        ORDER BY {TEACHER_CLASS_ROLE_PRIORITY_SQL}, id
                    ) AS duplicate_rank
                FROM bot_teacher_classes
            ) AS ranked_relations
            WHERE duplicate_rank > 1
        )
        """


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "bot_college_teacher",
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("college_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="manager", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["college_id"],
            ["bot_college.id"],
            name=op.f("fk_bot_college_teacher_college_id_bot_college"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["bot_teacher.id"],
            name=op.f("fk_bot_college_teacher_teacher_id_bot_teacher"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bot_college_teacher")),
        sa.UniqueConstraint("teacher_id", "college_id", name="uq_bot_college_teacher_teacher_college"),
        info={"bind_key": "models"},
    )

    connection = op.get_bind()
    unknown_roles = connection.execute(
        sa.text(unknown_duplicate_teacher_class_roles_sql())
    ).scalars().all()
    if unknown_roles:
        raise RuntimeError(
            "bot_teacher_classes 存在重复教师-班级关系且包含未知岗位，"
            f"请先人工清理后再迁移：{', '.join(str(role) for role in unknown_roles)}"
        )

    # 历史数据里如果有重复教师-班级关系，优先保留班主任/辅导员等管理岗位，
    # 同岗位再保留最早一条，避免迁移后静默丢失班级管理权限。
    op.execute(deduplicate_teacher_classes_sql())
    with op.batch_alter_table("bot_teacher_classes", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_bot_teacher_classes_teacher_class",
            ["teacher_id", "classes_id"],
        )


def downgrade(name: str = "") -> None:
    if name:
        return

    with op.batch_alter_table("bot_teacher_classes", schema=None) as batch_op:
        batch_op.drop_constraint("uq_bot_teacher_classes_teacher_class", type_="unique")
    op.drop_table("bot_college_teacher")
