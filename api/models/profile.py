import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func, text
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
    email_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    email_notifications_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_suppressed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_suppression_reason: Mapped[str | None] = mapped_column(String(32))
    telegram_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    filters = relationship("JobFilter", back_populates="profile", cascade="all, delete-orphan")
    matches = relationship("JobMatch", back_populates="profile", cascade="all, delete-orphan")
    telegram_link_tokens = relationship(
        "TelegramLinkToken", back_populates="profile", cascade="all, delete-orphan"
    )


class EmailSuppression(Base):
    __tablename__ = "email_suppressions"

    email: Mapped[str] = mapped_column(String(320), primary_key=True)
    reason: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32), server_default="resend")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailProviderEvent(Base):
    __tablename__ = "email_provider_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
