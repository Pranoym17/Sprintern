import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.database import Base
from api.models.base import TimestampMixin
from api.models.enums import JobSourceName


class SourceState(TimestampMixin, Base):
    __tablename__ = "source_states"
    __table_args__ = (UniqueConstraint("source", "source_key", name="uq_source_states_source_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[JobSourceName] = mapped_column(
        Enum(
            JobSourceName,
            native_enum=False,
            create_constraint=True,
            name="source_state_source_name",
            length=32,
            values_callable=lambda enum: [item.value for item in enum],
        )
    )
    source_key: Mapped[str] = mapped_column(String(255))
    cursor: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    backoff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
