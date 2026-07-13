import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base
from api.models.base import TimestampMixin
from api.models.enums import WorkMode


class JobFilter(TimestampMixin, Base):
    __tablename__ = "filters"
    __table_args__ = (Index("ix_filters_profile_active", "profile_id", "active"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100))
    role_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, server_default=text("'{}'::varchar[]")
    )
    location_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, server_default=text("'{}'::varchar[]")
    )
    terms: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)), default=list, server_default=text("'{}'::varchar[]")
    )
    work_mode: Mapped[WorkMode] = mapped_column(
        Enum(
            WorkMode,
            native_enum=False,
            create_constraint=True,
            name="filter_work_mode",
            length=16,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=WorkMode.ANY,
        server_default=WorkMode.ANY.value,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    profile = relationship("Profile", back_populates="filters")
