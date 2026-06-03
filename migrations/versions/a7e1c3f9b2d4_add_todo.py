"""add todo

迁移 ID: a7e1c3f9b2d4
父迁移: c3f2a8d9e4b1
创建时间: 2026-05-29 10:00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7e1c3f9b2d4"
down_revision: str | Sequence[str] | None = "c3f2a8d9e4b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "bot_todo",
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("remind_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["bot_user.id"],
            name=op.f("fk_bot_todo_owner_user_id_bot_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bot_todo")),
        info={"bind_key": "models"},
    )
    op.create_index(
        op.f("ix_bot_todo_owner_user_id"),
        "bot_todo",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bot_todo_status"),
        "bot_todo",
        ["status"],
        unique=False,
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_index(op.f("ix_bot_todo_status"), table_name="bot_todo")
    op.drop_index(op.f("ix_bot_todo_owner_user_id"), table_name="bot_todo")
    op.drop_table("bot_todo")
