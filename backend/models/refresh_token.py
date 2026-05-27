import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import UUID, Text, TIMESTAMP, ForeignKey
from models.upload import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id:         Mapped[uuid.UUID]       = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id:    Mapped[uuid.UUID]       = mapped_column(
        UUID, ForeignKey("users.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str]             = mapped_column(Text)
    created_at: Mapped[datetime]        = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime]        = mapped_column(TIMESTAMP(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    @property
    def is_valid(self) -> bool:
        return self.revoked_at is None and datetime.now(timezone.utc) < self.expires_at
