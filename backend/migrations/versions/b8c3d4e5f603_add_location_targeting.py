"""add location targeting

Revision ID: b8c3d4e5f603
Revises: a7b2c3d4e502
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8c3d4e5f603"
down_revision: str | Sequence[str] | None = "a7b2c3d4e502"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    cities = {
        "toronto": (43.6532, -79.3832),
        "vancouver": (49.2827, -123.1207),
        "montreal": (45.5019, -73.5674),
        "ottawa": (45.4215, -75.6972),
        "calgary": (51.0447, -114.0719),
        "edmonton": (53.5461, -113.4938),
        "waterloo": (43.4643, -80.5204),
        "kitchener": (43.4516, -80.4925),
        "halifax": (44.6488, -63.5752),
        "victoria": (48.4284, -123.3656),
        "winnipeg": (49.8951, -97.1384),
    }
    for city, (latitude, longitude) in cities.items():
        op.execute(
            "UPDATE jobs SET "
            f"latitude = {latitude}, longitude = {longitude} "
            f"WHERE latitude IS NULL AND normalized_location LIKE '%%{city}%%'"
        )
    op.create_index("ix_jobs_coordinates", "jobs", ["latitude", "longitude"])


def downgrade() -> None:
    op.drop_index("ix_jobs_coordinates", table_name="jobs")
