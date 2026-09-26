"""Add resolved locations and daily weather snapshots.

Revision ID: 20260927_0005
Revises: 20260925_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_0005"
down_revision: str | Sequence[str] | None = "20260925_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_preferences", sa.Column("location_label", sa.String(length=160), nullable=True)
    )
    op.add_column(
        "user_preferences",
        sa.Column("latitude", sa.Numeric(precision=8, scale=5), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("longitude", sa.Numeric(precision=8, scale=5), nullable=True),
    )
    op.add_column("user_preferences", sa.Column("timezone", sa.String(length=64), nullable=True))
    op.add_column(
        "user_preferences", sa.Column("temperature_unit", sa.String(length=10), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_user_preferences_temperature_unit_value"),
        "user_preferences",
        "temperature_unit IS NULL OR temperature_unit IN ('celsius', 'fahrenheit')",
    )
    op.create_check_constraint(
        op.f("ck_user_preferences_latitude_range"),
        "user_preferences",
        "latitude IS NULL OR latitude BETWEEN -90 AND 90",
    )
    op.create_check_constraint(
        op.f("ck_user_preferences_longitude_range"),
        "user_preferences",
        "longitude IS NULL OR longitude BETWEEN -180 AND 180",
    )

    # Snapshots were never written before this revision, so there is nothing to
    # de-duplicate ahead of the unique constraint.
    op.add_column(
        "weather_snapshots",
        sa.Column("temperature_min_celsius", sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column("weather_snapshots", sa.Column("weather_code", sa.Integer(), nullable=True))
    op.add_column(
        "weather_snapshots",
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint(
        "weather_user_forecast_at", "weather_snapshots", ["user_id", "forecast_at"]
    )


def downgrade() -> None:
    op.drop_constraint("weather_user_forecast_at", "weather_snapshots", type_="unique")
    op.drop_column("weather_snapshots", "fetched_at")
    op.drop_column("weather_snapshots", "weather_code")
    op.drop_column("weather_snapshots", "temperature_min_celsius")

    op.drop_constraint(
        op.f("ck_user_preferences_longitude_range"), "user_preferences", type_="check"
    )
    op.drop_constraint(
        op.f("ck_user_preferences_latitude_range"), "user_preferences", type_="check"
    )
    op.drop_constraint(
        op.f("ck_user_preferences_temperature_unit_value"), "user_preferences", type_="check"
    )
    op.drop_column("user_preferences", "temperature_unit")
    op.drop_column("user_preferences", "timezone")
    op.drop_column("user_preferences", "longitude")
    op.drop_column("user_preferences", "latitude")
    op.drop_column("user_preferences", "location_label")
