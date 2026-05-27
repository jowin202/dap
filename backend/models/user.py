import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import UUID, Text, Boolean, TIMESTAMP
from models.upload import Base


class User(Base):
    __tablename__ = "users"

    id:            Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    username:      Mapped[str]       = mapped_column(Text, unique=True)
    password_hash: Mapped[str]       = mapped_column(Text)
    created_at:    Mapped[datetime]  = mapped_column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    is_active:     Mapped[bool]      = mapped_column(Boolean, default=True)
