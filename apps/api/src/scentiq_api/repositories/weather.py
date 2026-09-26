"""Daily weather snapshots, always scoped to the authenticated user."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from scentiq_api.models import WeatherSnapshot

_REFRESHED_FIELDS = (
    "location_label",
    "temperature_celsius",
    "temperature_min_celsius",
    "humidity",
    "precipitation_probability",
    "weather_code",
    "condition",
    "source",
    "fetched_at",
)


def day_key(day: date) -> datetime:
    """A local calendar date stored as midnight UTC, so it keys uniquely."""
    return datetime.combine(day, time.min, tzinfo=UTC)


class WeatherRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_from(
        self,
        user_id: UUID,
        first_day: date,
        *,
        location_label: str,
        limit: int,
    ) -> list[WeatherSnapshot]:
        statement = (
            select(WeatherSnapshot)
            .where(
                WeatherSnapshot.user_id == user_id,
                WeatherSnapshot.location_label == location_label,
                WeatherSnapshot.forecast_at >= day_key(first_day),
            )
            .order_by(WeatherSnapshot.forecast_at)
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def get_day(self, user_id: UUID, day: date) -> WeatherSnapshot | None:
        return self._session.scalar(
            select(WeatherSnapshot).where(
                WeatherSnapshot.user_id == user_id,
                WeatherSnapshot.forecast_at == day_key(day),
            )
        )

    def upsert(self, snapshot: WeatherSnapshot) -> WeatherSnapshot:
        """Insert or overwrite the member's forecast for that day.

        A single `INSERT ... ON CONFLICT` so two requests refreshing the same
        forecast at once cannot race into a unique-constraint failure.
        """
        values = {
            "id": snapshot.id or uuid4(),
            "user_id": snapshot.user_id,
            "forecast_at": snapshot.forecast_at,
            **{field: getattr(snapshot, field) for field in _REFRESHED_FIELDS},
        }
        dialect = self._session.get_bind().dialect.name
        insert = postgresql_insert if dialect == "postgresql" else sqlite_insert
        statement = insert(WeatherSnapshot).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[WeatherSnapshot.user_id, WeatherSnapshot.forecast_at],
            set_={field: statement.excluded[field] for field in _REFRESHED_FIELDS},
        )
        self._session.execute(statement)
        stored = self.get_day(snapshot.user_id, snapshot.forecast_at.astimezone(UTC).date())
        assert stored is not None
        # The row may already be loaded from an earlier read in this session.
        self._session.refresh(stored)
        return stored

    def delete_from(self, user_id: UUID, first_day: date) -> None:
        """Drop forecasts for today onward, e.g. after the location changes.

        Past days are kept: they record what the weather was when a member wore
        something.
        """
        self._session.execute(
            delete(WeatherSnapshot).where(
                WeatherSnapshot.user_id == user_id,
                WeatherSnapshot.forecast_at >= day_key(first_day),
            )
        )
        self._session.flush()
