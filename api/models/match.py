import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.base import TimestampMixin
from api.models.enums import (
    DeliveryStatus,
    MatchStatus,
    NotificationCadence,
    NotificationChannel,
)


class JobMatch(TimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint("profile_id", "job_id", name="uq_matches_profile_job"),
        Index("ix_matches_profile_created", "profile_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT"), nullable=False
    )
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(
            MatchStatus,
            native_enum=False,
            create_constraint=True,
            name="match_status",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=MatchStatus.MATCHED,
        server_default=MatchStatus.MATCHED.value,
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile = relationship("Profile", back_populates="matches")
    job = relationship("Job", back_populates="matches")
    deliveries = relationship(
        "NotificationDelivery", back_populates="match", cascade="all, delete-orphan"
    )


class NotificationDelivery(TimestampMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("match_id", "channel", name="uq_deliveries_match_channel"),
        UniqueConstraint("idempotency_key", name="uq_delivery_idempotency_key"),
        Index("ix_deliveries_pending", "status", "next_attempt_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(
            NotificationChannel,
            native_enum=False,
            create_constraint=True,
            name="notification_channel",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    cadence: Mapped[NotificationCadence] = mapped_column(
        Enum(
            NotificationCadence,
            native_enum=False,
            create_constraint=True,
            name="delivery_cadence",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    recipient: Mapped[str] = mapped_column(String(320))
    idempotency_key: Mapped[str] = mapped_column(String(255))
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(
            DeliveryStatus,
            native_enum=False,
            create_constraint=True,
            name="delivery_status",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=DeliveryStatus.PENDING,
        server_default=DeliveryStatus.PENDING.value,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    match = relationship("JobMatch", back_populates="deliveries")


class TelegramLinkToken(Base):
    __tablename__ = "telegram_link_tokens"
    __table_args__ = (Index("ix_telegram_link_tokens_hash", "token_hash", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile = relationship("Profile", back_populates="telegram_link_tokens")
