import uuid

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.base import TimestampMixin
from api.models.enums import NotificationCadence


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    notification_cadence: Mapped[NotificationCadence] = mapped_column(
        Enum(
            NotificationCadence,
            native_enum=False,
            create_constraint=True,
            name="notification_cadence",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=NotificationCadence.INSTANT,
        server_default=NotificationCadence.INSTANT.value,
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), unique=True)

    filters = relationship("JobFilter", back_populates="profile", cascade="all, delete-orphan")
    matches = relationship("JobMatch", back_populates="profile", cascade="all, delete-orphan")
