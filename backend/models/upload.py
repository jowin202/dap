import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import UUID, Text, BigInteger, TIMESTAMP


class Base(DeclarativeBase):
    pass


class Upload(Base):
    __tablename__ = "uploads"

    id:         Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    token:      Mapped[uuid.UUID] = mapped_column(UUID, unique=True, default=uuid.uuid4)
    filename:   Mapped[str]       = mapped_column(Text)
    size_bytes: Mapped[int]       = mapped_column(BigInteger)
    created_at: Mapped[datetime]  = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    @property
    def is_valid(self) -> bool:
        if self.deleted_at:
            return False
        if self.expires_at is None:
            return True
        return datetime.now(timezone.utc) < self.expires_at
