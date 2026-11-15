"""refresh tokens: sha256 lookup instead of bcrypt scan

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alte Tokens sind bcrypt-gehasht und mit dem neuen SHA-256-Lookup nicht mehr auffindbar.
    op.execute("DELETE FROM refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", "refresh_tokens")
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.execute("DELETE FROM refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", "refresh_tokens")
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"],
                    postgresql_where="revoked_at IS NULL")
