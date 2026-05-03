"""add autogpt workflow checkpoint table

迁移 ID: 4bde1ea4c61a
父迁移: 1f7f0ab0d9c4, daaaf1e3068c
创建时间: 2026-05-03 22:30:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4bde1ea4c61a"
down_revision: str | Sequence[str] | None = ("1f7f0ab0d9c4", "daaaf1e3068c")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "bot_agent_workflow_checkpoint",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), server_default="", nullable=False),
        sa.Column("kind", sa.String(length=32), server_default="chat", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="planned", nullable=False),
        sa.Column("goal", sa.Text(), server_default="", nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("playbook_id", sa.String(length=64), nullable=True),
        sa.Column("playbook_name", sa.String(length=128), nullable=True),
        sa.Column("workflow_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bot_agent_workflow_checkpoint")),
        sa.UniqueConstraint("user_id", name=op.f("uq_bot_agent_workflow_checkpoint_user_id")),
        info={"bind_key": "models"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table("bot_agent_workflow_checkpoint")
