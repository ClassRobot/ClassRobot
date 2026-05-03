"""add autogpt workflow run history table

迁移 ID: 9bc9d0cbf59e
父迁移: 4bde1ea4c61a
创建时间: 2026-05-03 23:20:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9bc9d0cbf59e"
down_revision: str | Sequence[str] | None = "4bde1ea4c61a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "bot_agent_workflow_run",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("source_trace_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=32), server_default="chat", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="planned", nullable=False),
        sa.Column("goal", sa.Text(), server_default="", nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("playbook_id", sa.String(length=64), nullable=True),
        sa.Column("playbook_name", sa.String(length=128), nullable=True),
        sa.Column("approval_type", sa.String(length=32), server_default="none", nullable=False),
        sa.Column("approval_status", sa.String(length=32), server_default="not_required", nullable=False),
        sa.Column("approval_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("workflow_data", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bot_agent_workflow_run")),
        sa.UniqueConstraint("trace_id", name=op.f("uq_bot_agent_workflow_run_trace_id")),
        info={"bind_key": "models"},
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_table("bot_agent_workflow_run")
