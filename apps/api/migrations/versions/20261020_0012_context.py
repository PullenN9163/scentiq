"""Hourly forecasts and persistent event classification corrections."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0012"
down_revision = "20261007_0008_layer_stacks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "calendar_events",
        sa.Column("classification_source", sa.String(20), server_default="keyword", nullable=False),
    )
    op.add_column("weather_snapshots", sa.Column("hourly_forecast", sa.JSON(), nullable=True))
    op.add_column(
        "calendar_events",
        sa.Column(
            "classification_corrected", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("calendar_events", "classification_source")
    op.drop_column("calendar_events", "classification_corrected")
    op.drop_column("weather_snapshots", "hourly_forecast")
