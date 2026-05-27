"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id",         sa.UUID(),            nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("token",      sa.UUID(),            nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("filename",   sa.Text(),            nullable=False),
        sa.Column("size_bytes", sa.BigInteger(),      nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_uploads_expires_at", "uploads", ["expires_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_index("ix_uploads_token", "uploads", ["token"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    op.create_table(
        "users",
        sa.Column("id",            sa.UUID(),            nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username",      sa.Text(),            nullable=False),
        sa.Column("password_hash", sa.Text(),            nullable=False),
        sa.Column("created_at",    sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("is_active",     sa.Boolean(),         nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id",         sa.UUID(),            nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id",    sa.UUID(),            nullable=False),
        sa.Column("token_hash", sa.Text(),            nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"],
                    postgresql_where=sa.text("revoked_at IS NULL"))


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("users")
    op.drop_index("ix_uploads_token", "uploads")
    op.drop_index("ix_uploads_expires_at", "uploads")
    op.drop_table("uploads")
