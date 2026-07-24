from datetime import datetime
from typing import Literal

from api.schemas.common import APIModel


class PublicSourceStatus(APIModel):
    state: Literal["healthy", "stale", "unknown"]
    last_updated_at: datetime | None
