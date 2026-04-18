"""align organization and academic structure tables

迁移 ID: 1f7f0ab0d9c4
父迁移: ec39cb48b105
创建时间: 2026-04-18 14:30:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1f7f0ab0d9c4"
down_revision: str | Sequence[str] | None = "ec39cb48b105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _backfill_classes_school_and_major() -> None:
    connection = op.get_bind()

    classes_table = sa.table(
        "bot_classes",
        sa.column("id", sa.Integer()),
        sa.column("major", sa.String(length=64)),
        sa.column("college_id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
        sa.column("major_id", sa.Integer()),
    )
    college_table = sa.table(
        "bot_college",
        sa.column("id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
    )
    major_table = sa.table(
        "bot_major",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String(length=128)),
        sa.column("college_id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
    )

    rows = (
        connection.execute(
            sa.select(
                classes_table.c.id,
                classes_table.c.major,
                classes_table.c.college_id,
                classes_table.c.school_id,
                college_table.c.school_id.label("derived_school_id"),
            ).select_from(
                classes_table.outerjoin(
                    college_table,
                    classes_table.c.college_id == college_table.c.id,
                )
            )
        )
        .mappings()
        .all()
    )

    existing_major_rows = (
        connection.execute(
            sa.select(
                major_table.c.id,
                major_table.c.name,
                major_table.c.college_id,
            )
        )
        .mappings()
        .all()
    )
    major_map = {
        (row["college_id"], row["name"]): row["id"]
        for row in existing_major_rows
        if row["college_id"] is not None and row["name"]
    }

    for row in rows:
        class_id = row["id"]
        college_id = row["college_id"]
        major_name = (row["major"] or "").strip()
        derived_school_id = row["school_id"] or row["derived_school_id"]

        if row["school_id"] is None and derived_school_id is not None:
            connection.execute(
                sa.update(classes_table)
                .where(classes_table.c.id == class_id)
                .values(school_id=derived_school_id)
            )

        if not major_name or college_id is None or derived_school_id is None:
            continue

        key = (college_id, major_name)
        major_id = major_map.get(key)
        if major_id is None:
            result = connection.execute(
                sa.insert(major_table).values(
                    name=major_name,
                    college_id=college_id,
                    school_id=derived_school_id,
                )
            )
            major_id = result.inserted_primary_key[0]
            if major_id is None:
                major_id = connection.execute(
                    sa.select(major_table.c.id).where(
                        major_table.c.college_id == college_id,
                        major_table.c.name == major_name,
                    )
                ).scalar_one()
            major_map[key] = major_id

        connection.execute(
            sa.update(classes_table)
            .where(classes_table.c.id == class_id)
            .values(major_id=major_id)
        )


def _backfill_student_and_teacher_school() -> None:
    connection = op.get_bind()

    classes_table = sa.table(
        "bot_classes",
        sa.column("id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
    )
    student_table = sa.table(
        "bot_student",
        sa.column("id", sa.Integer()),
        sa.column("classes_id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
    )
    teacher_table = sa.table(
        "bot_teacher",
        sa.column("id", sa.Integer()),
        sa.column("college_id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
    )
    college_table = sa.table(
        "bot_college",
        sa.column("id", sa.Integer()),
        sa.column("school_id", sa.Integer()),
    )

    student_rows = (
        connection.execute(
            sa.select(
                student_table.c.id,
                student_table.c.school_id,
                classes_table.c.school_id.label("classes_school_id"),
            ).select_from(
                student_table.join(
                    classes_table,
                    student_table.c.classes_id == classes_table.c.id,
                )
            )
        )
        .mappings()
        .all()
    )
    for row in student_rows:
        if row["school_id"] is None and row["classes_school_id"] is not None:
            connection.execute(
                sa.update(student_table)
                .where(student_table.c.id == row["id"])
                .values(school_id=row["classes_school_id"])
            )

    teacher_rows = (
        connection.execute(
            sa.select(
                teacher_table.c.id,
                teacher_table.c.school_id,
                college_table.c.school_id.label("college_school_id"),
            ).select_from(
                teacher_table.outerjoin(
                    college_table,
                    teacher_table.c.college_id == college_table.c.id,
                )
            )
        )
        .mappings()
        .all()
    )
    for row in teacher_rows:
        if row["school_id"] is None and row["college_school_id"] is not None:
            connection.execute(
                sa.update(teacher_table)
                .where(teacher_table.c.id == row["id"])
                .values(school_id=row["college_school_id"])
            )


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "bot_major",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("college_id", sa.Integer(), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["college_id"],
            ["bot_college.id"],
            name="fk_bot_major_college_id_bot_college",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["bot_school.id"],
            name="fk_bot_major_school_id_bot_school",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bot_major"),
        sa.UniqueConstraint("college_id", "name", name="uq_bot_major_college_id_name"),
        info={"bind_key": "models"},
    )

    op.create_table(
        "bot_organization",
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("organization_type", sa.String(length=32), server_default="general", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["school_id"],
            ["bot_school.id"],
            name="fk_bot_organization_school_id_bot_school",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bot_organization"),
        sa.UniqueConstraint(
            "school_id",
            "organization_type",
            "name",
            name="uq_bot_organization_school_type_name",
        ),
        info={"bind_key": "models"},
    )

    op.create_table(
        "bot_organization_member",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("position", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.CheckConstraint(
            "(student_id IS NOT NULL AND teacher_id IS NULL) OR "
            "(student_id IS NULL AND teacher_id IS NOT NULL)",
            name="ck_bot_organization_member_subject",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["bot_organization.id"],
            name="fk_bot_organization_member_organization_id_bot_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["bot_student.id"],
            name="fk_bot_organization_member_student_id_bot_student",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["bot_teacher.id"],
            name="fk_bot_organization_member_teacher_id_bot_teacher",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_bot_organization_member"),
        sa.UniqueConstraint("organization_id", "student_id", name="uq_bot_organization_member_student"),
        sa.UniqueConstraint("organization_id", "teacher_id", name="uq_bot_organization_member_teacher"),
        info={"bind_key": "models"},
    )

    with op.batch_alter_table("bot_classes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("school_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("major_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_bot_classes_school_id_bot_school",
            "bot_school",
            ["school_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_bot_classes_major_id_bot_major",
            "bot_major",
            ["major_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _backfill_classes_school_and_major()
    _backfill_student_and_teacher_school()


def downgrade(name: str = "") -> None:
    if name:
        return

    with op.batch_alter_table("bot_classes", schema=None) as batch_op:
        batch_op.drop_constraint("fk_bot_classes_major_id_bot_major", type_="foreignkey")
        batch_op.drop_constraint("fk_bot_classes_school_id_bot_school", type_="foreignkey")
        batch_op.drop_column("major_id")
        batch_op.drop_column("school_id")

    op.drop_table("bot_organization_member")
    op.drop_table("bot_organization")
    op.drop_table("bot_major")
