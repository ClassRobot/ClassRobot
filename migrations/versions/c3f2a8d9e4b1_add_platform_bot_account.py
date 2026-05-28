"""add platform bot account

迁移 ID: c3f2a8d9e4b1
父迁移: b2f4d8a7c6e1
创建时间: 2026-05-27 20:30:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f2a8d9e4b1"
down_revision: str | Sequence[str] | None = "b2f4d8a7c6e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade(name: str = "") -> None:
    if name:
        return

    op.create_table(
        "bot_platform_bot_account",
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("encrypted_token", sa.Text(), nullable=False),
        sa.Column("base_url", sa.String(length=255), server_default="", nullable=False),
        sa.Column("wx_user_id", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="created", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_connected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["bot_user.id"],
            name=op.f("fk_bot_platform_bot_account_owner_user_id_bot_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bot_platform_bot_account")),
        sa.UniqueConstraint("platform", "account_id", name="uq_bot_platform_bot_account_platform_account"),
        info={"bind_key": "models"},
    )
    op.create_index(
        op.f("ix_bot_platform_bot_account_account_id"),
        "bot_platform_bot_account",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bot_platform_bot_account_platform"),
        "bot_platform_bot_account",
        ["platform"],
        unique=False,
    )


def downgrade(name: str = "") -> None:
    if name:
        return

    op.drop_index(op.f("ix_bot_platform_bot_account_platform"), table_name="bot_platform_bot_account")
    op.drop_index(op.f("ix_bot_platform_bot_account_account_id"), table_name="bot_platform_bot_account")
    op.drop_table("bot_platform_bot_account")
